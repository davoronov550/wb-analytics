from django.urls import path

from scheduling.adapters.inbound.http.views import ScheduleDetailView, ScheduleListView

urlpatterns = [
    path("schedules/", ScheduleListView.as_view(), name="schedule-list"),
    path("schedules/<int:schedule_id>/", ScheduleDetailView.as_view(), name="schedule-detail"),
]
