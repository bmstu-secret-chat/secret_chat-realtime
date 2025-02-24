from django.urls import include, path

from django_prometheus.exports import ExportToDjangoView

urlpatterns = [
    path("api/realtime/", include("realtime.router")),
    path("metrics", ExportToDjangoView, name="metrics"),
]
