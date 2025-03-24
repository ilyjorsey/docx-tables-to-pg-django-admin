from django.contrib import admin

from .models import Document402n, Test
from documents.utils.utils import UploadFileAdminMixin, ImportDocument402n


class Document402nAdmin(UploadFileAdminMixin, admin.ModelAdmin):
    model_class = Document402n
    model_importer = ImportDocument402n

    def get_urls(self):
        return super().get_urls()


admin.site.register(Document402n, Document402nAdmin)
admin.site.register(Test)
