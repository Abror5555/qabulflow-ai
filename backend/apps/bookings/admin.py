"""Django Admin — faqat ichki texnik zaxira vositasi (asosiy panel — React)."""

from django.contrib import admin

from apps.bookings.models import BookingEvent, Enrollment, TrialBooking

for model in (TrialBooking, BookingEvent, Enrollment):
    admin.site.register(model)
