def notifications_processor(request):
    if request.user.is_authenticated:
        notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:20]
    else:
        notifications = []
    return {'notificationss': notifications}