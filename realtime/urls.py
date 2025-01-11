from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/message/', include('message.urls')),
    path('api/realtime/', include('realtime.routing')),
]
