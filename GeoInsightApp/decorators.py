from functools import wraps
from django.http import HttpResponseForbidden
from .models import UserProfile

# Decorador para vistas que restringe el acceso a un conjunto de roles.
ROLE_ALIASES = {
    'admin': 'administrador'
}

def role_required(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Acceso denegado. Debes iniciar sesión.")

            # Permitir superusuarios siempre
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            try:
                user_profile = request.user.profile
                # Normalizar el rol usando alias
                normalized_role = ROLE_ALIASES.get(user_profile.role, user_profile.role)

                if normalized_role in allowed_roles:
                    return view_func(request, *args, **kwargs)
                else:
                    return HttpResponseForbidden(
                        f"Acceso denegado. Tu rol de '{user_profile.role}' no tiene permiso para ver esta página."
                    )
            except UserProfile.DoesNotExist:
                return HttpResponseForbidden("Acceso denegado. Tu cuenta de usuario no tiene un perfil asociado.")
            except AttributeError:
                return HttpResponseForbidden("Acceso denegado. No se pudo cargar tu perfil de usuario.")

        return _wrapped_view
    return decorator