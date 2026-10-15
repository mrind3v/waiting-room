from prometheus_client import Counter

BOOKING_CONFLICTS = Counter(
    "waitingroom_booking_conflicts_total",
    "Booking or reschedule attempts rejected because the slot was already taken",
)
APPOINTMENTS_BOOKED = Counter(
    "waitingroom_appointments_booked_total", "Appointments successfully booked"
)
TRANSITIONS = Counter(
    "waitingroom_appointment_transitions_total",
    "Appointment status transitions",
    ["to_status"],
)
