from django.conf.urls import patterns, include, url


urlpatterns = patterns('artist_dashboard.views',
    url(r'^toggle_recording_state/(?P<pk>\d+)/$', 'toggle_recording_state', name='recording_toggle'),
    url(r'^event/(?P<pk>\d+)-(?P<slug>[-\w]+)/edit/$', 'event_edit', name='event_edit'),
    url(r'^event/(?P<pk>\d+)-(?P<slug>[-\w]+)/$', 'event_detail', name='event_detail'),
    url(r'^edit-profile/$', 'edit_profile', name='edit_profile'),
    url(r'^settings/$', 'artist_settings', name='settings'),
    url(r'^my-events/$', 'my_gigs', name='my_gigs'),
    url(r'^legal-agreement/$', 'legal', name='legal'),
    url(r'^login/$', 'login', name='login'),
    url(r'^$', 'dashboard', name='home'),
)
