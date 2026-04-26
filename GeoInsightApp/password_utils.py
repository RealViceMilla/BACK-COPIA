from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

def collect_password_errors(password, user=None):
    if not password:
        return ["Debes ingresar una contrasena."]

    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        errors: list[str] = []
        for error in exc.error_list:
            code = getattr(error, "code", "")
            params = error.params if isinstance(error.params, dict) else {}

            if code == "password_too_short":
                min_length = params.get("min_length")
                if min_length:
                    errors.append(
                        f"La contrasena es demasiado corta. Debe tener al menos {min_length} caracteres." 
                    )
                else:
                    errors.append("La contrasena es demasiado corta.")
            elif code == "password_too_common":
                errors.append("La contrasena es muy comun. Elige una contrasena mas segura.")
            elif code == "password_entirely_numeric":
                errors.append("La contrasena no puede ser solo numeros.")
            elif code == "password_too_similar":
                verbose_name = params.get("verbose_name", "informacion personal")
                errors.append(f"La contrasena es demasiado parecida a tu {verbose_name}.")
            else:
                errors.append(str(error))
        return errors

    return []