import json
from django.db.models import F
from django.http import Http404, HttpResponse
from django.views.generic import ListView
from events.models import Recording


def json_error_response(error_message):
    return HttpResponse(json.dumps(dict(success=False,
                                        error_message=error_message)))


def update_media_viewcount(request):
    if not request.is_ajax():
        raise Http404()

    if request.method == "GET":
        return json_error_response("Only POST requests.")

    recording_id = request.POST.get('recording_id')

    try:
        recording = Recording.objects.get(id=recording_id)
    except:
        return Http404("Recording with that ID not found")

    recording.view_count = F('view_count') + 1
    recording.save()

    response = json.dumps({'status': True})
    return HttpResponse(response, content_type="application/json")


class MostPopularVideos(ListView):
    context_object_name = "recordings"
    queryset = Recording.objects.video().most_popular()[:30]
    template_name = "multimedia/archive-list.html"
    
    def get_context_data(self, **kwargs):
        context = super(MostPopularVideos, self).get_context_data(**kwargs)
        context['most_popular_videos'] = True
        return context

most_popular_videos = MostPopularVideos.as_view()


class MostRecentVideos(ListView):
    context_object_name = "recordings"
    queryset = Recording.objects.video().most_recent()[:30]
    template_name = "multimedia/archive-list.html"

    def get_context_data(self, **kwargs):
        context = super(MostRecentVideos, self).get_context_data(**kwargs)
        context['most_recent_videos'] = True
        return context

most_recent_videos = MostRecentVideos.as_view()


class MostPopularAudio(ListView):
    context_object_name = "recordings"
    queryset = Recording.objects.audio().most_popular()[:30]
    template_name = "multimedia/archive-list.html"

    def get_context_data(self, **kwargs):
        context = super(MostPopularAudio, self).get_context_data(**kwargs)
        context['most_popular_audio'] = True
        return context

most_popular_audio = MostPopularAudio.as_view()


class MostRecentAudio(ListView):
    context_object_name = "recordings"
    queryset = Recording.objects.audio().most_recent()[:30]
    template_name = "multimedia/archive-list.html"

    def get_context_data(self, **kwargs):
        context = super(MostRecentAudio, self).get_context_data(**kwargs)
        context['most_recent_audio'] = True
        return context

most_recent_audio = MostRecentAudio.as_view()
