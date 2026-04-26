from django import forms
from .models import Review, Visit, Evidence, Section, Group, UserProfile, Career, Semester, Course, GroupMember, Role
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.gis import forms as gis_forms
from django.contrib.auth.models import User

# Formulario para el inicio de sesión de usuarios
class LoginForm(AuthenticationForm):
    pass

# Formulario para crear o editar visitas, incluye validación y widgets GIS
class VisitForm(gis_forms.ModelForm):
    nombre = gis_forms.CharField(
        max_length=100,
        help_text="Nombre de la visita. Ej: 'Visita Empresa ABC - Semana 42'",
        widget=gis_forms.TextInput(attrs={
            'placeholder': 'Visita Empresa ABC - Semana 42',
            'class': 'input-field'
        })
    )

    descripcion = gis_forms.CharField(
        widget=gis_forms.Textarea(attrs={
            'placeholder': 'Descripción la visita ...',
            'rows': 4,
            'class': 'input-field'
        }),
        help_text="Descripción breve de la visita, incluyendo objetivos y actividades."
    )

    class Meta:
        model = Visit
        fields = ['nombre', 'descripcion', 'ubicacion', 'geofence']
        widgets = {
            'ubicacion': gis_forms.OSMWidget(attrs={
                'map_width': 600,
                'map_height': 400,
                'default_zoom': 12,
            }),
            'geofence': gis_forms.OSMWidget(attrs={
                'map_width': 600,
                'map_height': 400,
                'default_zoom': 12,
                'display_raw': True,
            })
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        import re
        pattern = r'^Visita .+ - Semana \d{1,2}$'
        if not re.match(pattern, nombre):
            raise gis_forms.ValidationError(
                "El nombre debe seguir el formato: 'Visita [Nombre Empresa] - Semana [número]'"
            )
        return nombre

# Formulario para subir o editar evidencias de estudiantes
class EvidenceForm(forms.ModelForm):
    class Meta:
        model = Evidence
        fields = ['visita', 'foto', 'descripcion', 'ubicacion_foto']
        widgets = {
            'descripcion': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Describe brevemente la evidencia...'
            }),
            'ubicacion_foto': forms.HiddenInput(),
        }

# Formulario para crear o editar revisiones de docentes
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['validado', 'comentarios']
        widgets = {
            'comentarios': forms.Textarea(attrs={'rows': 4}),
        }

# Formulario para crear o editar secciones de un curso
class SectionForm(forms.ModelForm):
    docentes = forms.ModelMultipleChoiceField(
        queryset=UserProfile.objects.filter(roles__name='docente'),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    class Meta:
        model = Section
        fields = ['nombre', 'course']

# Formulario para crear o editar grupos y asignar estudiantes
class GroupForm(forms.ModelForm):
    estudiantes = forms.ModelMultipleChoiceField(
        queryset=UserProfile.objects.filter(roles__name='estudiante'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Seleccionar estudiantes"
    )

    class Meta:
        model = Group
        fields = ['nombre', 'estudiantes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['estudiantes'].initial = UserProfile.objects.filter(
                user__in=self.instance.members.values_list('user', flat=True)
            )

    def save(self, commit=True, section=None):
        group = super().save(commit=False)
        if section:
            group.section = section
        if commit:
            group.save()
            GroupMember.objects.filter(group=group).delete()
            for userprofile in self.cleaned_data['estudiantes']:
                GroupMember.objects.create(group=group, user=userprofile.user)
        return group

# Formulario para crear o editar semestres
class SemesterForm(forms.ModelForm):
    class Meta:
        model = Semester
        fields = ['nombre', 'year']

# Formulario para crear o editar carreras
class CareerForm(forms.ModelForm):
    class Meta:
        model = Career
        fields = ['nombre', 'codigo']

# Formulario para crear o editar cursos, asignando docentes
class CourseForm(forms.ModelForm):
    docentes = forms.ModelMultipleChoiceField(
        queryset=UserProfile.objects.filter(roles__name='docente'),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    class Meta:
        model = Course
        fields = ['nombre', 'career', 'docentes']

# Formulario para editar datos básicos del usuario
class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        return email

# Formulario para editar perfil del usuario (roles, carrera, semestre, secciones)
class UserProfileForm(forms.ModelForm):
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    sections = forms.ModelMultipleChoiceField(
        queryset=Section.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = UserProfile
        fields = ['roles', 'semester', 'career', 'sections']
