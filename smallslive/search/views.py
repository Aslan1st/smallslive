import json
from collections import OrderedDict
from itertools import chain, groupby
import datetime
from dateutil import parser
from django.core.paginator import EmptyPage, Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.timezone import timedelta
from django.views.generic import View
from django.views.generic.base import TemplateView
from haystack.query import SearchQuerySet
from django.db.models import Q

from artists.models import Artist, Instrument
from events.models import Event, Venue

from .search import SearchObject
from .utils import facets_by_model_name


def search_autocomplete(request):
    sqs = SearchQuerySet().autocomplete(content=request.GET.get('term', '')).facet('model')
    artists = sqs.filter(model_exact="artist").load_all()[:5]
    events = sqs.filter(model_exact="event").order_by('-start').load_all()[:5]
    instruments = sqs.filter(model_exact="instrument").load_all()[:5]
    suggestions = [{'label': result.object.autocomplete_label(),
                    'sublabel': result.object.autocomplete_sublabel(),
                    'category': result.model_exact,
                    'url': result.object.get_absolute_url()} for result in chain(artists, events, instruments) if result]

    # Make sure you return a JSON object, not a bare list.
    # Otherwise, you could be vulnerable to an XSS attack.
    the_data = json.dumps({
        'counts': facets_by_model_name(sqs),
        'results': suggestions,
    }, sort_keys=True)
    resp = HttpResponse(the_data, content_type='application/json')
    return resp

def artist_form_autoconplete(request):
    artist_start = request.GET.get('artist-start', None)
    artist_qs = Artist.objects.filter(first_name__istartswith=artist_start)
    artist_list = []
    for artist in artist_qs:
        artist_data = {'full_name' : artist.full_name(), 'val': artist.pk}
        artist_list.append(artist_data)
    # Make sure you return a JSON object, not a bare list.
    # Otherwise, you could be vulnerable to an XSS attack.
    data = {
            'artist_list': artist_list
        }
    return JsonResponse(data)


class SearchMixin(object):

    def search(self, entity, main_search, page=1, order=None,
               instrument=None, date_from=None, date_to=None,
               artist_search=None, artist_pk=None, venue=None):

        search = SearchObject()

        if entity == Artist:
            results_per_page = 60 * 4
            sqs = search.search_artist(main_search, artist_search, instrument)

        elif entity == Event:
            results_per_page = 24

            sqs = search.search_event(main_search, order, date_from, date_to,
                                    artist_pk=artist_pk, venue=venue)
            if not self.request.user.is_superuser:
                sqs = sqs.filter(Q(state=Event.STATUS.Published) | Q(state=Event.STATUS.Cancelled))

        blocks = []
        block = []

        paginator = Paginator(sqs, results_per_page)

        try:
            objects = paginator.page(page).object_list
        except EmptyPage:
            objects = []

        for item in objects:
            object_item = entity.objects.filter(pk=item.pk).first()
            block.append(object_item)

            if len(block) == 6 and entity == Artist:
                blocks.append(block)
                block = []

        if block:
            blocks.append(block)
            block = []

        if paginator.count:
            
            actual_results = 1 + ((page - 1) * results_per_page) if entity == Artist else 1
            showing_results = paginator.count
        else:
            showing_results = 'NO RESULTS'

        return blocks, showing_results, paginator.num_pages


class UpcomingEventMixin(object):

    def get_upcoming_events_context_data(self, context):
        date_range_start = timezone.localtime(timezone.now())
        # if it's not night when events are still hapenning, show next day
        if date_range_start.hour > 6:
            date_range_start += timedelta(days=1)
        # don't show last nights events that are technically today
        date_range_start = date_range_start.replace(hour=10)
        events = Event.objects.filter(start__gte=date_range_start).order_by('start')
        if not self.request.user.is_staff:
            events = events.exclude(state=Event.STATUS.Draft)

        venue = self.request.GET.get('venue')
        if venue is not None:
            venue_id = int(venue)
            events = events.filter(venue__id=venue_id)
            context['venue_selected'] = venue_id

        # 30 events should be enough to show next 7 days with events
        events = events[:30]
        dates = {}
        for k, g in groupby(events, lambda e: e.listing_date()):
            dates[k] = list(g)
        sorted_dates = OrderedDict(sorted(dates.items(), key=lambda d: d[0])).items()[:7]
        context['next_7_days'] = sorted_dates
        most_recent = Event.objects.most_recent()[:20]
        if len(most_recent):
            context['new_in_archive'] = most_recent
        else:
            context['new_in_archive'] = Event.objects.exclude(
                state=Event.STATUS.Draft
            ).order_by('-start')[:20]
        context['venues'] = Venue.objects.all()
        return context


class MainSearchView(View, SearchMixin):

    def get(self, request, *args, **kwargs):
        # TODO: Why
        main_search = request.GET.get('main_search', None)
        artist_search = request.GET.get('artist_search', None)
        page = int(request.GET.get('page', 1))
        entity = self.kwargs.get('entity', None)
        order = request.GET.get('order', None)
        instrument = request.GET.get('instrument', None)
        date_from = request.GET.get('date_from', None)
        date_to = request.GET.get('date_to', None)
        artist_pk = request.GET.get('artist_pk', None)
        venue = request.GET.get('venue', None)
        partial = request.GET.get('partial', False)
        show_venue = request.GET.get('show_event_venue', False)
        show_sets = request.GET.get('show_event_setTime', False)
        upcoming = request.GET.get('is_upcoming', False)

        if date_from:
            date_from = parser.parse(date_from, fuzzy=True)
            if not date_from.tzinfo:
                date_from = timezone.make_aware(
                    date_from, timezone.get_current_timezone())
        if date_to:
            date_to = parser.parse(date_to, fuzzy=True)
            if not date_to.tzinfo:
                date_to = timezone.make_aware(
                    date_to, timezone.get_current_timezone())
 
        if entity == 'artist':
            artists_blocks, showing_results, num_pages = self.search(
                Artist, main_search, page, instrument=instrument, artist_search=artist_search)

            context = {
                'artists_blocks': artists_blocks,
                'query_term': main_search,
            }
            template = 'search/artist_results.html'

        elif entity == 'event':
            events, showing_results, num_pages = self.search(
                Event, main_search, page, order=order, date_from=date_from,
                date_to=date_to, artist_pk=artist_pk, venue=venue)

            context = {
                'events': events[0] if events else [],
                'secondary': True,
                'show_event_venue':show_venue,
                'show_extend_date': show_sets,
                'upcoming':  upcoming
            }
            template = ('search/event_search_row.html' if partial
                        else 'search/event_search_result.html')
        else:
            return Http404('entity does not exist')

        temp = render_to_string(
            template,
            context,
            context_instance=RequestContext(request)
        )

        data = {
            'template': temp,
            'showingResults': showing_results,
            'numPages': num_pages
        }

        if entity == 'event':
            context = {
                'actual_page': page,
                'last_page': num_pages,
                'range': range(1, num_pages + 1)[:page][-3:] + range(1, num_pages + 1)[page:][:2],
                'has_last_page': (num_pages - page) >= 3
            }

            if date_from and date_from > timezone.now().replace(hour=0, minute=0):
                context['show_venue_name'] = True

            template = 'search/page_numbers_footer.html'
            temp = render_to_string(
                template,
                context,
                context_instance=RequestContext(request)
            )
            data['pageNumbersFooter'] = temp

        return JsonResponse(data)


#
#   this is a proof of concept, once it is approved it will be refactored
#
class SearchBarView(View):

    def get(self, request, *args, **kwargs):
        main_search = request.GET.get('main_search', None)
        search = SearchObject()
        
        artists = []
        artist_results_per_page = 6
        sqs = search.search_artist(main_search)
        paginator = Paginator(sqs, artist_results_per_page)
        artists_results = paginator.count

        for item in paginator.page(1).object_list:
            item = Artist.objects.filter(pk=item.pk).first()
            artists.append(item)
        artists_results_left = artists_results - len(artists)
        
        events = []
        event_results_per_page = 8
        sqs = search.search_event(main_search)

        paginator = Paginator(sqs, event_results_per_page)
        events_results = paginator.count

        for item in paginator.page(1).object_list:
            item = Event.objects.filter(pk=item.pk).first()
            events.append(item)
        events_results_left = events_results - len(events)

        instruments = []
        instrument_results_per_page = 6
        sqs = search.get_instrument([main_search])
        paginator = Paginator(sqs, instrument_results_per_page)
        instruments_results = paginator.count

        for item in paginator.page(1).object_list:
            item = Instrument.objects.filter(pk=item.pk).first()
            instruments.append(item)

        context = {'artists': artists,
                   'artists_results': artists_results,
                   'artists_results_left': artists_results_left,
                   'events': events,
                   'events_results': events_results,
                   'events_results_left': events_results_left,
                   'instruments': instruments,
                   'instruments_results': instruments_results}
        template = 'search/search_bar_results.html'

        temp = render_to_string(template,
                                context,
                                context_instance=RequestContext(request)
                                )

        data = {
            'template': temp
        }

        return JsonResponse(data)


class TemplateSearchView(TemplateView, SearchMixin, UpcomingEventMixin):
    template_name = 'search/search.html'

    def get_context_data(self, **kwargs):
        context = super(TemplateSearchView, self).get_context_data(**kwargs)
        context = self.get_upcoming_events_context_data(context)
        q = self.request.GET.get('q', '')
        instrument = self.request.GET.get('instrument','')
        if q:
            context['musician_search'] = True

        artist_id = self.request.GET.get('artist_pk')
        if artist_id:
            artists_blocks = [[Artist.objects.filter(id=artist_id).first()]]
            showing_artist_results = ''
            num_pages = 1
        else:
            artists_blocks, showing_artist_results, num_pages = self.search(
                Artist, q, instrument=instrument)
        context['query_term'] = q
        instruments = [i.name for i in Instrument.objects.all()]

        context['instruments'] = instruments
        context['showing_artist_results'] = showing_artist_results
        context['artists_blocks'] = artists_blocks
        context['artist_num_pages'] = num_pages

        event_blocks, showing_event_results, num_pages = self.search(Event, q)

        context['showing_event_results'] = showing_event_results
        context['event_results'] = event_blocks[0] if event_blocks else []

        context['actual_page'] = page = 1
        context['last_page'] = num_pages
        context['range'] = range(
            1, num_pages + 1)[:page][-3:] + range(1, num_pages + 1)[page:][:2]
        context['has_last_page'] = (num_pages - page) >= 3
        default_to_date = 'now'
        if event_blocks and event_blocks[0] and event_blocks[0][0].date:
            default_to_date = event_blocks[0][0].date.strftime('%m/%d/%Y')
        context['default_from_date'] = timezone.now().strftime('%m/%d/%Y')
        context['default_to_date'] = default_to_date

        return context


class ArtistInfo(View):

    def get(self, request, *args, **kwargs):
        id = request.GET.get('id', None)

        artist = Artist.objects.filter(pk=id).first()

        context = {'artist': artist}
        template = 'artists/artist_detail_search.html'

        temp = render_to_string(template,
                                context,
                                context_instance=RequestContext(request)
                                )

        data = {
            'template': temp
        }

        return JsonResponse(data)


class UpcomingSearchView(SearchMixin):

    template_name = 'search/upcoming_calendar_dates.html'

    def get_context_data(self, **kwargs):
        context = super(UpcomingSearchView, self).get_context_data(**kwargs)
        context.update(self.get_upcoming_context)
        return context

    def get_upcoming_context(self):
        context = {'day_list': []}
        days = int(self.request.GET.get('days', 12))
        upcoming_page = int(self.request.GET.get('upcoming_page', 0))
        starting_date = self.request.GET.get('starting_date', datetime.datetime.today().strftime('%Y-%m-%d'))
        starting_date = datetime.datetime.strptime(starting_date, '%Y-%m-%d')
        starting_day = datetime.datetime(starting_date.year, starting_date.month, starting_date.day,3)
        venue = self.request.GET.get('venue', 'all')
        event_list = Event.objects.all()
        if venue:
            if venue != 'all':
                event_list = event_list.filter(venue__pk=venue)
        for day in range (0, days):
            day_itinerary = {}
            paged_day = day + days * upcoming_page 
            day_start = starting_date + timedelta(days=paged_day, hours=3)
            day_end = day_start + timedelta(days=1)
            day_itinerary['day_start'] = day_start
            day_itinerary['day_events'] = event_list.filter(start__gte=day_start, start__lte=day_end).order_by('start')
            context["day_list"].append(day_itinerary)
        return context
    
class UpcomingSearchViewAjax2(TemplateView, UpcomingSearchView):

    template_name = 'search/upcoming_calendar_dates.html'

    def get_context_data(self, **kwargs):
        context = super(UpcomingSearchViewAjax, self).get_context_data(**kwargs)
        context.update(self.get_upcoming_context())

        return context

class UpcomingSearchViewAjax(TemplateView, UpcomingSearchView):

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context.update(self.get_upcoming_context())
        data = {
            'template': render_to_string(
                'search/upcoming_calendar_dates.html', context,
                context_instance=RequestContext(request)
            )
        }
        
        return JsonResponse(data)
