from django.db.models.signals import post_save, m2m_changed, post_delete
from django.dispatch import receiver
import os
from .models import Year, Semester, Career, Section, UserProfile, Evidence, Visit, Group

# Sirve para crear automáticamente los semestres “Primavera” y “Otoño” para todas las carreras cada vez que se crea un nuevo año académico.
@receiver(post_save, sender=Year)
def create_semesters_for_year(sender, instance, created, **kwargs):
    if created:
        for nombre in ["Primavera", "Otoño"]:
            Semester.objects.create(
                year=instance,
                nombre=nombre
            )

# Actualizar UserProfile automáticamente cuando el admin asigna un estudiante a una sección.
@receiver(m2m_changed, sender=Section.estudiantes.through)
def update_profile_on_section_add(sender, instance, action, pk_set, **kwargs):
    if action != "post_add":
        return

    section = instance
    course = section.course
    career = course.career
    semester = course.semester

    for profile_id in pk_set:
        try:
            profile = UserProfile.objects.get(id=profile_id)
        except UserProfile.DoesNotExist:
            continue

        if not profile.email:
            profile.email = profile.user.email

        if not profile.career:
            profile.career = career

        if not profile.semester:
            profile.semester = semester

        profile.save()

# Señales para eliminar archivos de evidencias al eliminar instancias relacionadas
@receiver(post_delete, sender=Evidence)
def delete_evidence_file(sender, instance, **kwargs):

    if instance.foto and os.path.isfile(instance.foto.path):
        try:
            os.remove(instance.foto.path)
            print(f"Archivo eliminado: {instance.foto.path}")
        except OSError as e:
            print(f"Error al eliminar archivo: {e}")


@receiver(post_delete, sender=Visit)
def delete_visit_related_files(sender, instance, **kwargs):
    
    evidences = Evidence.objects.filter(visita=instance)
    for evidence in evidences:
        if evidence.foto and os.path.isfile(evidence.foto.path):
            try:
                os.remove(evidence.foto.path)
                print(f"Archivo relacionado con visita eliminado: {evidence.foto.path}")
            except OSError as e:
                print(f"Error al eliminar archivo relacionado: {e}")

@receiver(post_delete, sender=Group)
def delete_group_related_files(sender, instance, **kwargs):
    
    evidences = Evidence.objects.filter(group_member__group=instance)
    for evidence in evidences:
        if evidence.foto and os.path.isfile(evidence.foto.path):
            try:
                os.remove(evidence.foto.path)
                print(f"Archivo relacionado con grupo eliminado: {evidence.foto.path}")
            except OSError as e:
                print(f"Error al eliminar archivo relacionado: {e}")

@receiver(post_delete, sender=UserProfile)
def delete_user_related_files(sender, instance, **kwargs):
    
    evidences = Evidence.objects.filter(group_member__user=instance.user)
    for evidence in evidences:
        if evidence.foto and os.path.isfile(evidence.foto.path):
            try:
                os.remove(evidence.foto.path)
                print(f"Archivo relacionado con usuario eliminado: {evidence.foto.path}")
            except OSError as e:
                print(f"Error al eliminar archivo relacionado: {e}")