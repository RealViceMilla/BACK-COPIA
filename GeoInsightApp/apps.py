from django.apps import AppConfig

class GeoinsightappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'GeoInsightApp'

    def ready(self):
        # Importar signals
        import GeoInsightApp.signals
