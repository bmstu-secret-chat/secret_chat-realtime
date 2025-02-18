from django.urls import include, path

urlpatterns = [
    path("messenger/", include("messenger.urls", namespace="messenger")),
]
