from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.response import Response
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from GeoInsightApp.password_utils import collect_password_errors

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username_or_email = attrs.get('username')
        password = attrs.get('password')

        user = User.objects.filter(username=username_or_email).first()
        if not user:
            user = User.objects.filter(email=username_or_email).first()

        if not user:
            raise serializers.ValidationError('Credenciales invalidas')

        authenticated_user = authenticate(
            username=user.username,
            password=password
        )

        if authenticated_user is None:
            raise serializers.ValidationError('Credenciales invalidas')

        return super().validate({
            'username': user.username,
            'password': password
        })


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access = serializer.validated_data["access"]
        refresh = serializer.validated_data["refresh"]

        response = Response(
            {"detail": "Login exitoso"},
            status=200
        )

        response.set_cookie(
            key="access_token",
            value=access,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
            path="/",
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
            path="/",
        )

        return response


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 
    
    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        if not email:
            return Response({"detail": "Debes ingresar un correo"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_base = getattr(settings, "PASSWORD_RESET_FRONTEND_URL", "http://localhost:5173/reset-password")
            reset_link = f"{reset_base}?uid={uid}&token={token}"

            subject = "Recupera tu contrasena en GeoInsight"
            message = (
                "Hola,\n\n"
                "Recibimos una solicitud para restablecer tu contrasena. "
                f"Sigue el siguiente enlace para crear una nueva contrasena: {reset_link}\n\n"
                "Si no realizaste esta solicitud, puedes ignorar este correo.\n\n"
                "Saludos,\nEquipo GeoInsight"
            )

            send_mail(
                subject,
                message,
                getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@geoinsight.local"),
                [user.email],
                fail_silently=False,
            )

        return Response({"detail": "Se enviaron instrucciones para restablecer la contrasena, esto puede tomar unos minutos."})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [] 

    def post(self, request, *args, **kwargs):
        uid_b64 = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not all([uid_b64, token, new_password, confirm_password]):
            return Response({"detail": "Datos incompletos"}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"detail": "Las contrasenas no coinciden"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uid_b64))
            user = User.objects.get(pk=uid)
        except (ValueError, User.DoesNotExist, TypeError):
            return Response({"detail": "Solicitud invalida"}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Token invalido o expirado"}, status=status.HTTP_400_BAD_REQUEST)

        password_errors = collect_password_errors(new_password, user=user)
        if password_errors:
            return Response(
                {
                    "detail": "La contrasena no cumple con los requisitos.",
                    "errors": password_errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        return Response({"detail": "Contrasena actualizada con exito"})