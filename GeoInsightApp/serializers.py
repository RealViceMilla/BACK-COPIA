from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.auth.models import User
from django.db.models import Count
from .models import (
    Role, UserProfile, Course, Group, GroupMember, Company, Visit,
    Evidence, Review, Section, Career, Semester, Year
)
import json
from django.db import transaction

# Serializa datos básicos de usuarios de Django
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    career = serializers.SerializerMethodField()
    semester = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id", "username", "first_name", "last_name", "full_name",
            "email", "roles", "career", "semester"
        ]

    def get_full_name(self, obj):
        name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return name or obj.user.username

    def get_email(self, obj):
        return obj.user.email or obj.email or "No disponible"

    def get_roles(self, obj):
        return [role.name for role in obj.roles.all()]

    def get_career(self, obj):
        return obj.career.nombre if obj.career else "No disponible"

    def get_semester(self, obj):
        if not obj.semester:
            return "No disponible"
        year_name = obj.semester.year.nombre if obj.semester.year else "No disponible"
        return f"{obj.semester.nombre} - {year_name}"

# Serializa modelo Year
class YearSerializer(serializers.ModelSerializer):
    class Meta:
        model = Year
        fields = '__all__'

# Serializa modelo Semester
class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = '__all__'

# Serializa modelo Career
class CareerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Career
        fields = '__all__'

# Serializa modelo Course
class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = '__all__'

# Serializa secciones y sus estudiantes
class SectionSerializer(serializers.ModelSerializer):
    course = serializers.SerializerMethodField()
    students = serializers.SerializerMethodField()
    docentes = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = [
            "id",
            "nombre",
            "course",
            "students",
            "docentes",
            "students_count",
        ]

    def get_course(self, obj):
        course = obj.course
        if not course:
            return None

        career = getattr(course, "career", None)

        return {
            "id": course.id,
            "nombre": course.nombre,
            "career": {
                "id": career.id,
                "nombre": career.nombre,
            } if career else None,
        }

    def get_students(self, obj):
        estudiantes = obj.estudiantes.all()  # con prefetch en view

        return [
            {
                "id": estudiante.id,
                "full_name": (
                    f"{estudiante.user.first_name} {estudiante.user.last_name}".strip()
                    or estudiante.user.username
                ),
                "user": {
                    "id": estudiante.user.id,
                    "first_name": estudiante.user.first_name,
                    "last_name": estudiante.user.last_name,
                    "email": estudiante.user.email,
                },
                "rut": getattr(estudiante, "rut", None),
            }
            for estudiante in estudiantes
        ]

    def get_docentes(self, obj):
        docentes = obj.docentes.all()  # usa prefetch_related en la vista

        return [
            {
                "id": docente.id,
                "full_name": (
                    f"{docente.user.first_name} {docente.user.last_name}".strip()
                    or docente.user.username
                ),
                "user": {
                    "id": docente.user.id,
                    "username": docente.user.username,
                    "first_name": docente.user.first_name,
                    "last_name": docente.user.last_name,
                    "email": docente.user.email,
                },
            }
            for docente in docentes
        ]

    def get_students_count(self, obj):
        return obj.students_count #Aplicar codigo de ViewSet para contar estudiantes y evitar consultas adicionales
    
# Serializa miembros de grupo
class GroupMemberSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = GroupMember
        fields = ['id', 'user']

    def get_user(self, obj):
        return {"id": obj.user.id, "username": obj.user.username}

# Serializador para creación de miembros de grupo
class GroupMemberCreateSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all())
    user = serializers.IntegerField(write_only=True)

    class Meta:
        model = GroupMember
        fields = ['id', 'group', 'user']

    def validate(self, data):
        user_id = data.get("user")
    
        user = User.objects.filter(id=user_id).first()
        if user:
            data["user"] = user
            return data
    
        profile = UserProfile.objects.filter(id=user_id).first()
        if profile:
            data["user"] = profile.user
            return data
    
        raise serializers.ValidationError({"user": "Usuario no encontrado."})

    def create(self, validated_data):
        group = validated_data["group"]
        user = validated_data["user"]
    
        if GroupMember.objects.filter(group__section=group.section, user=user).exists():
            raise serializers.ValidationError(
                {"detail": "El usuario ya es miembro de un grupo en esta sección."}
            )
    
        return GroupMember.objects.create(**validated_data)

# Serializa visitas incluyendo geofence y ubicación en GeoJSON
class VisitSerializer(serializers.ModelSerializer):
    sections = serializers.SerializerMethodField()
    creado_por = serializers.CharField(source="creado_por.user.username", read_only=True)
    geofence = serializers.SerializerMethodField()
    geofence_wkt = serializers.CharField(write_only=True, required=False)
    ubicacion = serializers.SerializerMethodField()
    ubicacion_wkt = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Visit
        fields = [
            "id", "nombre", "descripcion", "creado_por",
            "ubicacion", "ubicacion_wkt",
            "geofence", "geofence_wkt",
            "sections", "fecha_visita",
        ]

    def create(self, validated_data):
        ubicacion_wkt = validated_data.pop("ubicacion_wkt", None)
        geofence_wkt = validated_data.pop("geofence_wkt", None)

        from django.contrib.gis.geos import GEOSGeometry

        if ubicacion_wkt:
            validated_data["ubicacion"] = GEOSGeometry(ubicacion_wkt, srid=4326)
        if geofence_wkt:
            validated_data["geofence"] = GEOSGeometry(geofence_wkt, srid=4326)

        visit = Visit.objects.create(**validated_data)
        return visit

    def get_geofence(self, obj):
        if obj.geofence:
            try:
                return json.loads(obj.geofence.geojson)
            except Exception:
                return None
        return None

    def get_ubicacion(self, obj):
        if obj.ubicacion:
            try:
                return json.loads(obj.ubicacion.geojson)
            except Exception:
                return None
        return None

    def get_sections(self, obj):
        return [
            {
                "id": s.id,
                "nombre": s.nombre,
                "course": s.course.nombre if s.course else None
            }
            for s in obj.sections.all()
        ]

# Serializa evidencias de estudiantes y sus reviews
class EvidenceSerializer(serializers.ModelSerializer):
    group_name = serializers.SerializerMethodField()
    section_name = serializers.SerializerMethodField()
    visita = VisitSerializer(read_only=True)
    review = serializers.SerializerMethodField()
    imagenes = serializers.SerializerMethodField()
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Evidence
        fields = [
            "id",
            "group",
            "group_name",
            "section_name",
            "visita",
            "descripcion",
            "estado",
            "ubicacion_foto",
            "imagenes",
            "review",
            "en_geofence",
            "tomado_en",
            "created_by",
        ]
        read_only_fields = ["created_by", "estado", "en_geofence", "tomado_en"]

    def get_group_name(self, obj):
        if not obj.group:
            return None
        return obj.group.nombre

    def get_section_name(self, obj):
        if not obj.group or not obj.group.section:
            return None
        return obj.group.section.nombre

    def get_review(self, obj):
        review = obj.review if hasattr(obj, "review") else None
        if not review:
            return None
        return ReviewSerializer(review, context=self.context).data

    def get_imagenes(self, obj):
        request = self.context.get("request")

        return [
            request.build_absolute_uri(img.imagen.url) if request else img.imagen.url
            for img in obj.imagenes.all()
            if img.imagen
        ]

# Serializa revisiones de evidencias (GET)
class ReviewSerializer(serializers.ModelSerializer):
    evidencia = serializers.SerializerMethodField()
    docente = UserProfileSerializer(read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "evidencia",
            "docente",
            "validado",
            "rechazada",
            "comentarios",
            "fecha_revision",
        ]

    def get_evidencia(self, obj):
        evidencia = getattr(obj, "evidencia", None)
        if not evidencia:
            return None

        return {
            "id": evidencia.id,
            "descripcion": evidencia.descripcion,
            "estado": evidencia.estado,
            "grupo": self._get_grupo(evidencia),
            "visita": self._get_visita(evidencia),
            "tomado_en": evidencia.tomado_en,
        }

    def _get_grupo(self, evidencia):
        group = getattr(evidencia, "group", None)
        if not group:
            return None

        return {
            "id": group.id,
            "nombre": group.nombre,
        }

    def _get_visita(self, evidencia):
        visita = getattr(evidencia, "visita", None)
        if not visita:
            return None

        return {
            "id": visita.id,
            "nombre": visita.nombre,
        }

# Serializador para crear revisiones de evidencias (POST)
class ReviewCreateSerializer(serializers.ModelSerializer):
    evidencia = serializers.PrimaryKeyRelatedField(queryset=Evidence.objects.all())
    validado = serializers.BooleanField()

    class Meta:
        model = Review
        fields = ['evidencia', 'validado', 'rechazada', 'comentarios']

    def validate(self, attrs):
        if attrs.get('validado') and attrs.get('rechazada'):
            raise serializers.ValidationError("No se puede aprobar y rechazar al mismo tiempo.")
        if not attrs.get('validado') and not attrs.get('rechazada'):
            raise serializers.ValidationError("Debe marcar como aprobado o rechazado.")
        return attrs

# Serializa creación de grupos
class GroupCreateSerializer(serializers.ModelSerializer):
    section_id = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(),
        source="section"
    )

    class Meta:
        model = Group
        fields = ["id", "nombre", "section_id"]

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "nombre": instance.nombre,
            "section": {
                "id": instance.section.id,
                "nombre": instance.section.nombre,
                "course": instance.section.course.nombre if instance.section.course else None,
            },
            "members": GroupMemberSerializer(instance.members.all(), many=True).data
        }

# Serializa grupos completos con miembros, evidencias y revisiones
class GroupSerializer(serializers.ModelSerializer):
    section = SectionSerializer(read_only=True)
    members = GroupMemberSerializer(many=True, read_only=True)
    evidences = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "nombre", "section", "members", "evidences", "reviews"]

    def get_evidences(self, obj):
        evidencias = obj.evidences.all()
        return EvidenceSerializer(
            evidencias, 
            many=True, 
            context=self.context 
        ).data

    def get_reviews(self, obj):
        revisiones = Review.objects.filter(evidencia__group=obj)
        return ReviewSerializer(revisiones, many=True, context=self.context).data

# Serializa compañías con ubicación geoespacial
class CompanySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Company
        geo_field = 'ubicacion'
        fields = '__all__'


#NUEVOS SERIALIZERS PARA ADMINISTRACION
class AdminCourseSerializer(serializers.ModelSerializer):
    career_nombre = serializers.CharField(source='career.nombre', read_only=True)
    semester_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = ['id', 'nombre', 'career', 'semester', 'career_nombre', 'semester_nombre'] 
        
    def get_semester_nombre(self, obj):
        if obj.semester and obj.semester.year:
            return f"{obj.semester.nombre} {obj.semester.year.nombre}"
        elif obj.semester:
            return obj.semester.nombre
        return "N/A"

class AdminSectionSerializer(serializers.ModelSerializer):
    course = serializers.SerializerMethodField()
    docentes = serializers.SerializerMethodField()
    estudiantes = serializers.SerializerMethodField()
    course_nombre = serializers.CharField(source='course.nombre', read_only=True)
    career_nombre = serializers.CharField(source='course.career.nombre', read_only=True)
    docentes_nombres = serializers.SerializerMethodField()
    course_id = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), source='course', write_only=True, required=True)
    docentes_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    estudiantes_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = Section
        fields = [
            'id',
            'nombre',
            'course',
            'docentes',
            'estudiantes',
            'course_nombre',
            'career_nombre',
            'docentes_nombres',
            'course_id',
            'docentes_ids',
            'estudiantes_ids',
        ]

    def get_course(self, obj):
        if not obj.course:
            return None
        career = obj.course.career
        return {
            "id": obj.course.id,
            "nombre": obj.course.nombre,
            "career": {
                "id": career.id,
                "nombre": career.nombre,
            } if career else None,
        }

    def get_docentes(self, obj):
        docentes = obj.docentes.select_related("user")
        return [
            {
                "id": docente.id,
                "full_name": f"{docente.user.first_name} {docente.user.last_name}".strip()
                or docente.user.username,
                "user": {
                    "id": docente.user.id,
                    "username": docente.user.username,
                    "first_name": docente.user.first_name,
                    "last_name": docente.user.last_name,
                    "email": docente.user.email,
                },
            }
            for docente in docentes
        ]

    def get_estudiantes(self, obj):
        estudiantes = obj.estudiantes.select_related("user")
        return [
            {
                "id": estudiante.id,
                "full_name": f"{estudiante.user.first_name} {estudiante.user.last_name}".strip()
                or estudiante.user.username,
                "user": {
                    "id": estudiante.user.id,
                    "username": estudiante.user.username,
                    "first_name": estudiante.user.first_name,
                    "last_name": estudiante.user.last_name,
                    "email": estudiante.user.email,
                },
                "rut": getattr(estudiante, "rut", None),
                "username": estudiante.user.username,
            }
            for estudiante in estudiantes
        ]

    def get_docentes_nombres(self, obj):
        docentes = obj.docentes.all()
        return ", ".join(
            f"{p.user.first_name} {p.user.last_name}".strip() or p.user.username
            for p in docentes
        )

    def create(self, validated_data):
        docentes_ids = validated_data.pop('docentes_ids', [])
        estudiantes_ids = validated_data.pop('estudiantes_ids', [])
        section = Section.objects.create(**validated_data)
        
        if docentes_ids:
            section.docentes.set(docentes_ids)
        if estudiantes_ids:
            section.estudiantes.set(estudiantes_ids)
        
        return section

    def update(self, instance, validated_data):
        docentes_ids = validated_data.pop('docentes_ids', [])
        estudiantes_ids = validated_data.pop('estudiantes_ids', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if docentes_ids is not None:
            instance.docentes.set(docentes_ids)
        if estudiantes_ids is not None:
            instance.estudiantes.set(estudiantes_ids)
        
        return instance

class UserProfileAdminSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username')
    email = serializers.EmailField(source='user.email')
    first_name = serializers.CharField(source='user.first_name', required=False, allow_blank=True)
    last_name = serializers.CharField(source='user.last_name', required=False, allow_blank=True)
    is_active = serializers.BooleanField(source='user.is_active', required=False) 
    password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'}) 
    
    roles = serializers.SlugRelatedField(
        many=True, 
        queryset=Role.objects.all(), 
        slug_field='name' 
    )

    class Meta:
        model = UserProfile
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'password', 'is_active', 'roles', 
            'career', 'semester' 
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        roles_data = validated_data.pop('roles')
        password = user_data.pop('password', None)
        
        with transaction.atomic():
            user = User.objects.create(**user_data)
            if password:
                user.set_password(password)
                user.save()
            
            profile = UserProfile.objects.create(user=user, **validated_data)
            profile.roles.set(roles_data)
            return profile

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        roles_data = validated_data.pop('roles', None)
        user = instance.user
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()
        if roles_data is not None:
            instance.roles.set(roles_data)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class VisitManagementSerializer(serializers.ModelSerializer):
    creado_por = serializers.CharField(source="creado_por.user.username", read_only=True)
    sections = serializers.PrimaryKeyRelatedField(queryset=Section.objects.all(), many=True)
    ubicacion = serializers.SerializerMethodField()
    geofence = serializers.SerializerMethodField()
    ubicacion_wkt = serializers.CharField(write_only=True, required=False)
    geofence_wkt = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Visit
        fields = [
            "id", "nombre", "descripcion", "creado_por",
            "ubicacion", "ubicacion_wkt",
            "geofence", "geofence_wkt",
            "sections", "fecha_visita",
        ]

    def get_ubicacion(self, obj):
        if obj.ubicacion:
            try:
                return json.loads(obj.ubicacion.geojson)
            except:
                return None
        return None

    def get_geofence(self, obj):
        if obj.geofence:
            try:
                return json.loads(obj.geofence.geojson)
            except:
                return None
        return None

    def create(self, validated_data):
        ubicacion_wkt = validated_data.pop("ubicacion_wkt", None)
        geofence_wkt = validated_data.pop("geofence_wkt", None)
        sections = validated_data.pop("sections", [])

        if ubicacion_wkt:
            validated_data["ubicacion"] = GEOSGeometry(ubicacion_wkt, srid=4326)
        if geofence_wkt:
            validated_data["geofence"] = GEOSGeometry(geofence_wkt, srid=4326)

        visit = Visit.objects.create(**validated_data)
        visit.sections.set(sections)
        return visit

    def update(self, instance, validated_data):
        ubicacion_wkt = validated_data.pop("ubicacion_wkt", None)
        geofence_wkt = validated_data.pop("geofence_wkt", None)
        sections = validated_data.pop("sections", None)

        if ubicacion_wkt:
            instance.ubicacion = GEOSGeometry(ubicacion_wkt, srid=4326)
        if geofence_wkt:
            instance.geofence = GEOSGeometry(geofence_wkt, srid=4326)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if sections is not None:
            instance.sections.set(sections)

        instance.save()
        return instance

class TeacherSerializer(serializers.ModelSerializer):
    nombres = serializers.CharField(source="user.first_name")
    apellidos = serializers.CharField(source="user.last_name")
    carrera = serializers.CharField(source="career.nombre", read_only=True)
    secciones_asignadas = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ["id", "nombres", "apellidos", "carrera", "secciones_asignadas"]

    def get_secciones_asignadas(self, obj):
        return [{
            "id": s.id,
            "nombre": s.nombre,
            "curso": s.course.nombre,
            "carrera": s.course.career.nombre,
        } for s in obj.sections_as_docente.all()]
        
        
# Serializador dedicado para VCM (copia de AdminSectionSerializer pero separado)
class VCMSectionSerializer(serializers.ModelSerializer):
    course = serializers.SerializerMethodField()
    docentes = serializers.SerializerMethodField()
    estudiantes = serializers.SerializerMethodField()
    course_nombre = serializers.CharField(source='course.nombre', read_only=True)
    career_nombre = serializers.CharField(source='course.career.nombre', read_only=True)
    docentes_nombres = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = [
            'id',
            'nombre',
            'course',
            'docentes',
            'estudiantes',
            'course_nombre',
            'career_nombre',
            'docentes_nombres',
        ]

    def get_course(self, obj):
        if not obj.course:
            return None
        career = obj.course.career
        return {
            "id": obj.course.id,
            "nombre": obj.course.nombre,
            "career": {
                "id": career.id,
                "nombre": career.nombre,
            } if career else None,
        }

    def get_docentes(self, obj):
        docentes = obj.docentes.select_related("user")
        return [
            {
                "id": docente.id,
                "full_name": f"{docente.user.first_name} {docente.user.last_name}".strip()
                or docente.user.username,
                "user": {
                    "id": docente.user.id,
                    "username": docente.user.username,
                    "first_name": docente.user.first_name,
                    "last_name": docente.user.last_name,
                    "email": docente.user.email,
                },
            }
            for docente in docentes
        ]

    def get_estudiantes(self, obj):
        estudiantes = obj.estudiantes.select_related("user")
        return [
            {
                "id": estudiante.id,
                "full_name": f"{estudiante.user.first_name} {estudiante.user.last_name}".strip()
                or estudiante.user.username,
                "user": {
                    "id": estudiante.user.id,
                    "username": estudiante.user.username,
                    "first_name": estudiante.user.first_name,
                    "last_name": estudiante.user.last_name,
                    "email": estudiante.user.email,
                },
                "rut": getattr(estudiante, "rut", None),
                "username": estudiante.user.username,
            }
            for estudiante in estudiantes
        ]

    def get_docentes_nombres(self, obj):
        docentes = obj.docentes.all()
        return ", ".join(
            f"{p.user.first_name} {p.user.last_name}".strip() or p.user.username
            for p in docentes
        )
