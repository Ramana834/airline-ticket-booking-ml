from django.urls import path
from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.my_bookings, name="my_bookings"),
    path("history/", views.history, name="history"),

    path("review/<int:flight_id>/", views.review, name="review"),
    path("seat/<int:flight_id>/", views.select_seat, name="select_seat"),  # ✅ FIXED
    path("seat-status/<int:flight_id>/", views.seat_status_api, name="seat_status_api"),
    path("payment/", views.payment, name="payment"),
    path("success/", views.success, name="success"),

    path("ticket/<int:booking_id>/", views.ticket, name="ticket"),
    path("ticket/<int:booking_id>/pdf/", views.ticket_pdf, name="ticket_pdf"),

    path("ticket/outbound/", views.ticket_outbound, name="ticket_outbound"),
    path("ticket/return/", views.ticket_return, name="ticket_return"),

    path("cancel/<int:booking_id>/", views.cancel_booking, name="cancel_booking"),

    path("select-outbound/<int:flight_id>/", views.select_outbound, name="select_outbound"),
    path("select-return/<int:flight_id>/", views.select_return, name="select_return"),

    path("refund/<int:booking_id>/", views.process_refund, name="process_refund"),

    path("hotels/book/", views.book_hotel, name="book_hotel"),
    path("hotels/", views.my_hotel_bookings, name="my_hotel_bookings"),
]
