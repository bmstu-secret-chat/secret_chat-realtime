from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


@api_view(["POST"])
def send_message(request):
    """Отправка сообщения"""
    user_id = request.data.get("user_id")
    message = request.data.get("message")

    if not user_id:
        return Response(
            {"error": "user_id отсутствует"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not message:
        return Response(
            {"error": "message отсутствует"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    return Response({"message": f"Сообщение от пользователя {user_id}: {message}"}, status=status.HTTP_200_OK)
