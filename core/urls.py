# """
# URL configuration for core project.
# """
# from django.contrib import admin
# from django.urls import path, include
# from django.conf import settings
# from django.conf.urls.static import static
# from . import views

# urlpatterns = [
#     path('', views.home_view, name='home'),
#     path('admin/', admin.site.urls),
#     path('accounts/', include('accounts.urls')),
#     path('interviews/', include('interviews.urls')),
#     path('resumes/', include('resumes.urls')),
#     path('forum/', include('forums.urls')),
#     path('api/auth/', include('accounts.urls')),  # API endpoints
#     # path('api/profiles/', include('profiles.urls')),
#     # path('api/interviews/', include('interviews.urls')),
#     # path('api/companies/', include('companies.urls')),
#     # path('api/forums/', include('forums.urls')),
#     # path('api/ai-feedback/', include('ai_feedback.urls')),
#     # path('api/resumes/', include('resumes.urls')),
# ]

# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
#     urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


"""
URL configuration for core project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("interviews/", include("interviews.urls")),
    path("resumes/", include("resumes.urls")),
    path("forums/", include("forums.urls")),
    path("api/auth/", include("accounts.urls")),  # API endpoints
    # path('api/profiles/', include('profiles.urls')),
    # path('api/interviews/', include('interviews.urls')),
    # path('api/companies/', include('companies.urls')),
    # path('api/forums/', include('forums.urls')),
    # path('api/ai-feedback/', include('ai_feedback.urls')),
    # path('api/resumes/', include('resumes.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
