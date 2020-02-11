from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.generic.base import RedirectView, TemplateView

from gmmp import settings

admin.site.site_header = settings.ADMIN_SITE_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_SITE_TITLE
admin.site.site_url = settings.ADMIN_SITE_SITE_URL
admin.site.index_title = settings.ADMIN_SITE_INDEX_TITLE

urlpatterns = [
    path('grappelli/', include('grappelli.urls')), # grappelli URLS
    re_path(r'^jet/', include('jet.urls', 'jet')),  # Django JET URLS
    re_path(r'^jet/dashboard/', include('jet.dashboard.urls', 'jet-dashboard')),  # Django JET dashboard URLS
    path(
        'admin/password_reset/',
        auth_views.PasswordResetView.as_view(),
        name='admin_password_reset',
    ),
    path(
        'admin/password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(),
        name='password_reset_complete',
    ),
    path('admin/', admin.site.urls), # Admin site URLS

    re_path(r'^$', RedirectView.as_view(url='/admin'), name='go-to-admin'),

    # TODO: Fix reports views, they're blocking migration
    # url(r'^reports/', include('reports.urls')),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
