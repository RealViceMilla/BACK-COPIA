from django.db.models.signals import post_save, m2m_changed, post_delete
from django.dispatch import receiver
import os
from .models import Year, Semester, Section, UserProfile, Evidence, Visit, Group, Review, EvidenceImage

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

@receiver(post_delete, sender=Review)
def reset_evidence_state(sender, instance, **kwargs):
    Evidence.objects.filter(pk=instance.evidencia_id).update(
        estado='pendiente'
    )

@receiver(post_delete, sender=EvidenceImage)
def delete_image_file(sender, instance, **kwargs):
    if instance.imagen:
        try:
            if os.path.isfile(instance.imagen.path):
                os.remove(instance.imagen.path)
        except OSError as e:
            print(f"Error eliminando imagen: {e}")