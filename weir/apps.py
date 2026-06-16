from django.apps import AppConfig


class WeirConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'weir'
    verbose_name = '鱼梁管理系统'

    def ready(self):
        import weir.signals
