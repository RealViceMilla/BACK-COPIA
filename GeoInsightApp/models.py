from django.contrib.gis.db import models as gis_models
from django.contrib.auth.models import User
from django.db import models, transaction
from django.core.exceptions import ValidationError

# Modelo de roles de usuario
class Role(models.Model):
    name = models.CharField(max_length=50, unique=True, choices=[
        ('estudiante', 'Estudiante'),
        ('docente', 'Docente Responsable'),
        ('admin', 'Administrador'),
        ('supervisor_vcm', 'Supervisor VcM'),
        ('fg', 'Formación General'),
    ])

    def __str__(self):
        return self.get_name_display()

# Perfil extendido de usuario con roles, carrera y semestre
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    roles = models.ManyToManyField('Role', related_name='users')
    email = models.EmailField(unique=True, null=True, blank=True)
    semester = models.ForeignKey('Semester', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    career = models.ForeignKey('Career', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')

    def __str__(self):
        full_name = self.user.get_full_name() or self.user.username
        roles = ', '.join([r.get_name_display() for r in self.roles.all()])
        semester_info = f" - {self.semester}" if self.semester else ""
        career_info = f" - {self.career}" if self.career else ""
        return f"{full_name} ({roles}){semester_info}{career_info}"

# Modelo de año académico
class Year(models.Model):
    nombre = models.CharField(max_length=20, unique=True)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.nombre

# Modelo de semestre asociado a un año académico
class Semester(models.Model):
    year = models.ForeignKey(Year, on_delete=models.CASCADE, related_name='semesters', null=True)
    nombre = models.CharField(max_length=50)
    
    def __str__(self):
        return f"{self.nombre} {self.year.nombre}"

# Modelo de carrera universitaria
class Career(models.Model):
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=20, unique=True)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='careers')
    
    def __str__(self):
        return f"{self.nombre} - {self.semester}"

# Modelo de asignatura o curso
class Course(models.Model):
    nombre = models.CharField(max_length=200)
    career = models.ForeignKey(Career, on_delete=models.CASCADE, related_name='courses')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='courses')

    def __str__(self):
        return f"{self.nombre} - {self.career.nombre}"

# Modelo de sección de un curso
class Section(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sections')
    nombre = models.CharField(max_length=50)
    docentes = models.ManyToManyField(UserProfile, related_name="sections_as_docente", blank=True)
    estudiantes = models.ManyToManyField(UserProfile, related_name="sections_as_student", blank=True)
    
    def __str__(self):
        return f"{self.course.nombre} - {self.nombre}"

    @property
    def estudiantes_asignados(self):
        return ", ".join([u.user.username for u in self.estudiantes.all()])

# Modelo de grupo dentro de una sección
class Group(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='groups')
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.section} - {self.nombre}"

# Modelo de miembro de grupo
class GroupMember(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')

    class Meta:
        unique_together = ('group', 'user')

    def __str__(self):
        return f"{self.group} :: {self.user.username}"

# Modelo de empresa con ubicación geoespacial
class Company(models.Model):
    nombre = models.CharField(max_length=200)
    direccion = models.CharField(max_length=250, blank=True)
    ubicacion = gis_models.PointField(help_text='Ubicación principal (lat/lng) de la empresa', srid=4326)

    def __str__(self):
        return self.nombre

# Modelo de visita a empresas o proyectos
class Visit(models.Model):
    creado_por = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    fecha_visita = models.DateTimeField(auto_now_add=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    ubicacion = gis_models.PointField(srid=4326)
    geofence = gis_models.PolygonField(srid=4326, null=True, blank=True)
    sections = models.ManyToManyField(Section, related_name='visitas')

    def __str__(self):
        return f'Visita {self.nombre} de {self.creado_por.user.username} el {self.fecha_visita.date()} '

# Modelo de evidencia enviada por estudiantes (se elimino foto, se usara nueva tabla para imágenes)
class Evidence(models.Model):
    ESTADOS_EVIDENCIA = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='evidences') # Se asocia la evidencia a un grupo específico
    visita = models.ForeignKey('Visit', on_delete=models.CASCADE, related_name='evidences') 
    descripcion = models.TextField(blank=True, null=True)
    tomado_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS_EVIDENCIA, default='pendiente')
    ubicacion_foto = gis_models.PointField(srid=4326, blank=True, null=True)
    en_geofence = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True) # Para ver quién creó la evidencia

    def validar_geocerca(self):
        if not self.visita_id or not self.ubicacion_foto:
            return False
        if self.visita.geofence:
            return self.visita.geofence.contains(self.ubicacion_foto)
        return False

    def save(self, *args, **kwargs):
        self.en_geofence = (
            self.visita_id is not None
            and self.ubicacion_foto is not None
            and self.validar_geocerca()
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return (self.descripcion or "")[:50]

class EvidenceImage(models.Model):
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE, related_name='imagenes')
    imagen = models.ImageField(upload_to='evidencias/')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            with transaction.atomic():
                count = EvidenceImage.objects.select_for_update().filter(
                    evidence=self.evidence
                ).count()

                if count >= 3:
                    raise ValidationError("Solo se permiten 3 imágenes por evidencia")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Imagen de evidencia {self.evidence_id}"

# Modelo de revisión de evidencias por docentes
class Review(models.Model):
    evidencia = models.OneToOneField(Evidence, on_delete=models.CASCADE, related_name='review')
    docente = models.ForeignKey('UserProfile', on_delete=models.CASCADE, related_name='reviews')
    validado = models.BooleanField(default=False)
    rechazada = models.BooleanField(default=False)
    comentarios = models.TextField(blank=True, null=True)
    fecha_revision = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.validado and self.rechazada:
            raise ValidationError("No puede estar validado y rechazado al mismo tiempo")

    def save(self, *args, **kwargs):
        self.full_clean()

        with transaction.atomic():
            super().save(*args, **kwargs)

            estado = 'pendiente'

            if self.validado:
                estado = 'aprobada'
            elif self.rechazada:
                estado = 'rechazada'

            Evidence.objects.filter(pk=self.evidencia_id).update(estado=estado)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            Evidence.objects.filter(pk=self.evidencia_id).update(estado='pendiente')
            super().delete(*args, **kwargs)

    def __str__(self):
        return f"Review evidencia {self.evidencia_id}"