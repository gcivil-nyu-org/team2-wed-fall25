"""
WebSocket URL routing for interviews app.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/interview/behavioral-resume/$",
        consumers.BehavioralResumeLiveConsumer.as_asgi(),
    ),
]
