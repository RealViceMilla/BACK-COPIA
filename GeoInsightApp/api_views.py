# ------------------------------------------------------------------------
# api_views.py - API REST para acceder y manipular los datos de los modelos
# ------------------------------------------------------------------------
import json
import os
import zipfile
from io import BytesIO

import openpyxl
from django.contrib.gis.geos import GEOSGeometry
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework_gis.filters import DistanceToPointFilter

from .models import (
    Career, Company, Course, Evidence, Group, GroupMember, Review, Section, Semester, UserProfile, Visit, Year
)
from .serializers import (
    AdminCourseSerializer,
    AdminSectionSerializer,
    CompanySerializer,
    CareerSerializer,
    CourseSerializer,
    EvidenceSerializer,
    GroupCreateSerializer,
    GroupMemberCreateSerializer,
    GroupMemberSerializer,
    GroupSerializer,
    ReviewCreateSerializer,
    ReviewSerializer,
    SectionSerializer,
    SemesterSerializer,
    TeacherSerializer,
    UserProfileAdminSerializer,
    UserProfileSerializer,
    VisitManagementSerializer,
    VisitSerializer,
    YearSerializer,
    VCMSectionSerializer
)


def format_user(user, default="N/A"):
    if not user:
        return default
    full_name = (user.get_full_name() or "").strip()
    username = getattr(user, "username", "") or default
    return full_name or username


def format_datetime(value, fmt="%Y-%m-%d %H:%M", default="N/A"):
    if not value:
        return default
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime(fmt)


def format_date(value, fmt="%Y-%m-%d", default="N/A"):
    return format_datetime(value, fmt=fmt, default=default)


# ViewSet para gestión de perfiles de usuario y roles
class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        profile = UserProfile.objects.get(user=request.user)
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

# ViewSet para gestión de carreras (solo lectura)
class CareerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Career.objects.all()
    serializer_class = CareerSerializer
    filterset_fields = ['codigo', 'semester']

# ViewSet para gestión de semestres (solo lectura)
class SemesterViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Semester.objects.all()
    serializer_class = SemesterSerializer
    filterset_fields = ['year']

# ViewSet para gestión de cursos/asignaturas
class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    filterset_fields = ['career']

# ViewSet para gestión de secciones de cursos
class SectionViewSet(viewsets.ReadOnlyModelViewSet):
    base_prefetch = ["estudiantes__user", "docentes__user"]

    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["course__career"]
    search_fields = ["nombre", "course__nombre"]

    def get_queryset(self):
        params = self.request.query_params
        user = self.request.user
        career_id = params.get("career")
        student_id = params.get("student")

        qs = (
            Section.objects
            .select_related("course", "course__career")
            .prefetch_related(*self.base_prefetch)
            .distinct()
        )

        if career_id:
            return qs.filter(course__career_id=career_id)

        if student_id:
            return qs.filter(estudiantes__user__id=student_id)

        profile = getattr(user, "profile", None)
        if not profile:
            return qs.none()

        if profile.roles.filter(name__iexact="admin").exists() or profile.roles.filter(name__iexact="supervisor_vcm").exists():
            return qs

        if profile.roles.filter(name__iexact="docente").exists():
            return qs.filter(docentes__id=profile.id)

        if profile.roles.filter(name__iexact="estudiante").exists():
            return qs.filter(estudiantes__id=profile.id)

        return qs.none()

    @action(detail=False, methods=["get"], url_path="teacher")
    def teacher_sections(self, request):
        profile = getattr(request.user, "profile", None)

        if not profile or not profile.roles.filter(name__iexact="docente").exists():
            return Response([], status=200)

        secciones = (
            Section.objects
            .filter(docentes=profile)
            .select_related("course", "course__career")
            .prefetch_related(*self.base_prefetch)
            .distinct()
        )

        serializer = self.get_serializer(secciones, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="student")
    def student_sections(self, request):
        profile = getattr(request.user, "profile", None)
    
        if not profile or not profile.roles.filter(name__iexact="estudiante").exists():
            return Response([], status=200)
    
        secciones = (
            Section.objects
            .filter(estudiantes=profile)
            .select_related("course", "course__career")
            .prefetch_related(*self.base_prefetch)
            .distinct()
        )
    
        serializer = self.get_serializer(secciones, many=True)
        return Response(serializer.data)
        
# ViewSet para gestión de grupos dentro de secciones
class GroupViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return GroupCreateSerializer
        return GroupSerializer

    def get_queryset(self):
        qs = Group.objects.all().prefetch_related(
            "members__user",
            "members__evidence_set__visita",
            "section__course",
            "section__docentes",
        )

        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile is None:
            return qs.none()

        student_id = self.request.query_params.get("student")
        section_id = self.request.query_params.get("section")
        if student_id:
            qs = qs.filter(members__user__id=student_id)
        if section_id:
            qs = qs.filter(section_id=section_id)

        if self.action == "list":
            if profile.roles.filter(name__iexact="docente").exists():
                qs = qs.filter(section__docentes=profile)
            elif profile.roles.filter(name__iexact="estudiante").exists():
                qs = qs.filter(members__user=user)

        return qs.distinct()

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset()).select_related(
            "section__course"
        ).prefetch_related(
            "members__user",
            "members__evidence_set__visita",
            "section__docentes",
        )

        try:
            obj = queryset.get(pk=self.kwargs["pk"])
        except Group.DoesNotExist:
            raise Http404("Group not found")

        self.check_object_permissions(self.request, obj)
        return obj

    @action(detail=False, methods=["get"], url_path="section/(?P<section_id>[^/.]+)")
    def list_by_section(self, request, section_id=None):
        """Lista los grupos de una sección específica."""
        user = request.user
        profile = getattr(user, "profile", None)

        if profile and profile.roles.filter(name__iexact="docente").exists():
            if not profile.sections_as_docente.filter(id=section_id).exists():
                return Response(
                    {"detail": "No tienes permiso para ver grupos de esta sección."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif profile and profile.roles.filter(name__iexact="supervisor_vcm").exists():
            pass
        else:
            return Response(
                {"detail": "No tienes permiso para ver grupos de esta sección."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        grupos = Group.objects.filter(section_id=section_id).prefetch_related(
            "members__user",
            "members__evidence_set__visita",
            "section__course",
        )
        serializer = self.get_serializer(grupos, many=True)
        return Response(serializer.data)

# ViewSet para gestión de integrantes de grupos
class GroupMemberViewSet(viewsets.ModelViewSet):
    queryset = GroupMember.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return GroupMemberCreateSerializer
        return GroupMemberSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = serializer.save()
        return Response(GroupMemberSerializer(member).data, status=201)

# ViewSet para gestión de empresas
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]  
    filterset_fields = ['nombre']
    filter_backends = (DistanceToPointFilter,)

# ViewSet para gestión de visitas
class VisitViewSet(viewsets.ModelViewSet):
    queryset = Visit.objects.all()
    serializer_class = VisitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("sections", "creado_por")
        section_id = self.request.query_params.get("section")
        if section_id:
            qs = qs.filter(sections__id=section_id).distinct()
        return qs

    def perform_create(self, serializer):
        profile = UserProfile.objects.get(user=self.request.user)
        data = self.request.data

        ubicacion_wkt = data.get("ubicacion_wkt")
        geofence_wkt = data.get("geofence_wkt")

        ubicacion_geom = GEOSGeometry(ubicacion_wkt, srid=4326) if ubicacion_wkt else None
        geofence_geom = GEOSGeometry(geofence_wkt, srid=4326) if geofence_wkt else None

        visit = serializer.save(
            creado_por=profile,
            ubicacion=ubicacion_geom,
            geofence=geofence_geom
        )

        sections_ids = data.get("sections", [])
        if isinstance(sections_ids, str):
            try:
                sections_ids = json.loads(sections_ids)
            except Exception:
                sections_ids = []

        if sections_ids:
            visit.sections.set(sections_ids)
        visit.save()

# ViewSet para gestión de evidencias de estudiantes
class EvidenceViewSet(viewsets.ModelViewSet):
    queryset = Evidence.objects.all()
    serializer_class = EvidenceSerializer
    filterset_fields = ["visita", "group_member", "estado", "en_geofence"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Evidence.objects.all().select_related("group_member__user", "visita")

        career_id = self.request.query_params.get("career")
        section_id = self.request.query_params.get("section")
        visit_id = self.request.query_params.get("visit")

        if visit_id:
            qs = qs.filter(visita_id=visit_id)

        if section_id:
            qs = qs.filter(visita__sections__id=section_id)

        if career_id:
            qs = qs.filter(visita__sections__course__career_id=career_id)

        return qs.distinct()

    def perform_create(self, serializer):
        user = self.request.user
        group_id = self.request.data.get("group_member")
        visita_id = self.request.data.get("visit")
        ubicacion_wkt = self.request.data.get("ubicacion_foto")
    
        group_member = GroupMember.objects.filter(group_id=group_id, user=user).first()
        if not group_member:
            raise ValidationError("No se encontró un miembro de grupo válido para este usuario.")
        visita = Visit.objects.filter(id=visita_id).first()
        if not visita:
            raise ValidationError("Visita inválida o no encontrada.")
    
        existing_evidences = Evidence.objects.filter(group_member__group_id=group_id, visita=visita)
        if existing_evidences.filter(estado="rechazada").exists():
            raise ValidationError("No se pueden subir más evidencias para esta visita porque existe una evidencia rechazada.")

        if existing_evidences.count() >= 3:
            raise ValidationError("El grupo ya ha subido el máximo de 3 evidencias para esta visita.")
    
        ubicacion_geom = GEOSGeometry(ubicacion_wkt, srid=4326) if ubicacion_wkt else None
        serializer.save(group_member=group_member, visita=visita, ubicacion_foto=ubicacion_geom)

    @action(detail=False, methods=["get"], url_path="pendientes")
    def pendientes(self, request):
        qs = Evidence.objects.filter(review__isnull=True).select_related("group_member__user", "visita")
        
        career_id = request.query_params.get("career")
        section_id = request.query_params.get("section")
        visit_id = request.query_params.get("visit")
        
        if visit_id:
            qs = qs.filter(visita_id=visit_id)
        
        if section_id:
            qs = qs.filter(visita__sections__id=section_id)
        
        if career_id:
            qs = qs.filter(visita__sections__course__career_id=career_id)
        
        qs = qs.distinct()
        
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

# ViewSet para gestión de revisiones de docentes
class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related(
        "evidencia",
        "evidencia__visita",
        "docente__user"
    )
    filterset_fields = ["evidencia", "docente", "validado", "rechazada"]

    def get_serializer_class(self):
        if self.action == "create":
            return ReviewCreateSerializer
        return ReviewSerializer

    def perform_create(self, serializer):
        docente_profile = UserProfile.objects.get(user=self.request.user)
        review = serializer.save(docente=docente_profile)
        evidencia = review.evidencia

        if review.validado:
            evidencia.estado = "aprobada"
        elif review.rechazada:
            evidencia.estado = "rechazada"
        else:
            evidencia.estado = "pendiente"
        evidencia.save(update_fields=["estado"])

        review.fecha_revision = timezone.now()
        review.save(update_fields=["fecha_revision"])
    
    @action(detail=False, methods=["get"], url_path="history")
    def history(self, request):

        qs = self.queryset.all()

        career_id = request.query_params.get("career")
        section_id = request.query_params.get("section")
        visit_id = request.query_params.get("visit")

        if visit_id:
            qs = qs.filter(evidencia__visita_id=visit_id)

        if section_id:
            qs = qs.filter(evidencia__visita__sections__id=section_id)

        if career_id:
            qs = qs.filter(evidencia__visita__sections__course__career_id=career_id)

        qs = qs.distinct()
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
    


#NUEVOS API_VIEWS PARA ADMINISTRACION
class YearViewSet(viewsets.ModelViewSet):
    queryset = Year.objects.all().order_by('-nombre') 
    serializer_class = YearSerializer
    permission_classes = [IsAuthenticated] 

class AdminSemesterViewSet(viewsets.ModelViewSet):
    queryset = Semester.objects.all().order_by('-year__nombre', 'nombre') 
    serializer_class = SemesterSerializer
    permission_classes = [IsAuthenticated]

class AdminCareerViewSet(viewsets.ModelViewSet):
    queryset = Career.objects.all().order_by('nombre') 
    serializer_class = CareerSerializer
    permission_classes = [IsAuthenticated]

class AdminCourseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated] 
    queryset = Course.objects.all().select_related('career', 'semester__year').order_by('career__nombre', 'nombre') 
    serializer_class = AdminCourseSerializer
    filterset_fields = ['career', 'semester']
    search_fields = ['nombre', 'career__nombre']

class AdminSectionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = (
        Section.objects
        .select_related('course__career', 'course__semester__year')
        .prefetch_related('docentes__user')
        .order_by('course__nombre', 'nombre')
    )
    serializer_class = AdminSectionSerializer
    filterset_fields = ['course', 'docentes', 'course__career']
    search_fields = [
        'nombre',
        'course__nombre',
        'course__career__nombre',
        'docentes__user__first_name',
        'docentes__user__last_name',
        'docentes__user__username',
    ]

class UserProfileAdminViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileAdminSerializer 
    permission_classes = [IsAuthenticated] 

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role')

        if role:
            queryset = queryset.filter(roles__name=role)

        return queryset

    @action(detail=False, methods=['post'], url_path='change_password')
    def change_password(self, request):
        profile_id = request.data.get('profile_id') 
        new_password = request.data.get('new_password')

        if not profile_id or not new_password:
            return Response({'error': 'Faltan profile_id y/o new_password.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            profile = UserProfile.objects.select_related('user').get(pk=profile_id) 
            user = profile.user
        except UserProfile.DoesNotExist:
            return Response({'error': 'Perfil de usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
            
        user.set_password(new_password)
        user.save()
        
        return Response({'success': 'Contraseña cambiada con éxito.'}, status=status.HTTP_200_OK)

    def perform_destroy(self, instance):
        user = instance.user
        if user:
            user.delete()
        else:
            super().perform_destroy(instance)

class VisitManagementViewSet(viewsets.ModelViewSet):
    queryset = Visit.objects.all().prefetch_related("sections", "creado_por")
    serializer_class = VisitManagementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        section_id = self.request.query_params.get("section")
        career_id = self.request.query_params.get("career")
        year_id = self.request.query_params.get("year")

        if section_id:
            qs = qs.filter(sections__id=section_id).distinct()

        if career_id:
            qs = qs.filter(sections__course__career_id=career_id).distinct()

        if year_id:
            qs = qs.filter(sections__course__semester__year_id=year_id).distinct()

        return qs

    def perform_create(self, serializer):
        profile = UserProfile.objects.get(user=self.request.user)
        data = self.request.data

        ubicacion_wkt = data.get("ubicacion_wkt")
        geofence_wkt = data.get("geofence_wkt")

        ubicacion_geom = GEOSGeometry(ubicacion_wkt, srid=4326) if ubicacion_wkt else None
        geofence_geom = GEOSGeometry(geofence_wkt, srid=4326) if geofence_wkt else None

        visit = serializer.save(
            creado_por=profile,
            ubicacion=ubicacion_geom,
            geofence=geofence_geom
        )

        sections_ids = data.get("sections", [])
        if isinstance(sections_ids, str):
            try:
                sections_ids = json.loads(sections_ids)
            except Exception:
                sections_ids = []

        if sections_ids:
            visit.sections.set(sections_ids)

        visit.save()

    def perform_update(self, serializer):
        data = self.request.data
        instance = self.get_object()

        ubicacion_wkt = data.get("ubicacion_wkt")
        geofence_wkt = data.get("geofence_wkt")

        if ubicacion_wkt:
            instance.ubicacion = GEOSGeometry(ubicacion_wkt, srid=4326)

        if geofence_wkt:
            instance.geofence = GEOSGeometry(geofence_wkt, srid=4326)

        visit = serializer.save()

        sections_ids = data.get("sections", None)
        if sections_ids is not None:
            if isinstance(sections_ids, str):
                try:
                    sections_ids = json.loads(sections_ids)
                except Exception:
                    sections_ids = []
            visit.sections.set(sections_ids)

        visit.save()

        
        
class DocenteAssignViewSet(viewsets.ViewSet):

    def list(self, request):
        docentes = UserProfile.objects.filter(
            roles__name="docente"
        ).prefetch_related("sections_as_docente")

        serializer = TeacherSerializer(docentes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="disponibles")
    def disponibles(self, request, pk=None):
        disponibles = Section.objects.all()

        serializer = AdminSectionSerializer(disponibles, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="asignar")
    def asignar(self, request, pk=None):
        docente = UserProfile.objects.filter(
            id=pk, roles__name="docente"
        ).first()

        if not docente:
            return Response({"error": "Docente no encontrado"}, status=404)

        secciones_ids = request.data.get("secciones", [])

        secciones = Section.objects.filter(id__in=secciones_ids)

        docente.sections_as_docente.set(secciones)

        return Response({"message": "Asignación actualizada con éxito"})
    
    
    @action(detail=False, methods=["get"], url_path="filtrar")
    def filtrar(self, request):
        queryset = Section.objects.all()

        nombre = request.query_params.get("nombre")
        curso = request.query_params.get("curso")
        carrera = request.query_params.get("carrera")

        if nombre:
            queryset = queryset.filter(nombre__icontains=nombre)
        if curso:
            queryset = queryset.filter(course__nombre__icontains=curso)
        if carrera:
            queryset = queryset.filter(course__career__nombre__icontains=carrera)

        serializer = AdminSectionSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=["get"], url_path="carreras")
    def carreras(self, request):
        carreras = Career.objects.all().values("id", "nombre")
        return Response(list(carreras))

    @action(detail=False, methods=["get"], url_path="cursos-por-carrera")
    def cursos_por_carrera(self, request):
        carrera_id = request.query_params.get("carrera_id")

        if not carrera_id:
            return Response({"error": "Debe enviar carrera_id"}, status=400)

        cursos = Course.objects.filter(career_id=carrera_id).values("id", "nombre")
        return Response(list(cursos))

    @action(detail=False, methods=["get"], url_path="secciones-por-curso")
    def secciones_por_curso(self, request):
        curso_id = request.query_params.get("curso_id")

        if not curso_id:
            return Response({"error": "Debe enviar curso_id"}, status=400)

        secciones = Section.objects.filter(course_id=curso_id)
        serializer = AdminSectionSerializer(secciones, many=True)

        return Response(serializer.data)


# ViewSet para VCM
class VCMSectionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Section.objects
        .select_related('course__career', 'course__semester__year')
        .prefetch_related('docentes__user')
        .order_by('course__nombre', 'nombre')
    )
    serializer_class = VCMSectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        profile = getattr(user, "profile", None)
        if profile and profile.roles.filter(name__iexact="supervisor_vcm").exists():
            return qs 
        return qs.none()  