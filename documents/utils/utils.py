import csv
import logging
import os
import tempfile
import time

import pandas as pd
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django.utils.translation import gettext as _
from docx import Document

# from documents.utils.additional_utils import MkbRubricsParser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='utils.log',
                    filemode='a')


class UploadFileAdminMixin(admin.ModelAdmin):
    """
    Mixin for adding file upload functionality to the database from the admin panel.
    """

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [path(
            'upload/', self.admin_site.admin_view(self.upload_file), name="upload_file")
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['has_upload_method'] = hasattr(self, 'upload_file')

        return super().changelist_view(request, extra_context=extra_context)

    def upload_file(self, request):
        if request.method == 'POST' and request.FILES.get('file'):
            file = request.FILES.get('file')

            if not file.name.endswith('.docx'):
                messages.error(request, _('The file must be in DOCX format.'))

            start_time = time.time()
            try:
                model_class = getattr(self, 'model_class', None)
                model_importer = getattr(self, 'model_importer', None)

                processor = model_importer(file, model_class)
                processor.docx_to_csv()

                end_time = time.time()
                elapsed_time = end_time - start_time

                elapsed_time_message = f'{elapsed_time:.2f} seconds'

                messages.success(request,
                                 _('File successfully uploaded. Processing time: {}').format(elapsed_time_message))

                return redirect('admin:%s_%s_changelist' % (self.model._meta.app_label, self.model._meta.model_name))

            except ValueError as ve:
                messages.error(request, _('Validation error: {}').format(str(ve)))

            except FileNotFoundError:
                messages.error(request, _('File not found.'))

            except Exception as e:
                messages.error(request, _('Error while updating document: {}').format(str(e)))
        else:
            messages.error(request, _('No file selected or an error occurred during upload.'))

        return self.changelist_view(request)


class DocxToDB:
    """
    Algorithm for loading data from a DOCX document into the database.

    Args:
        docx_path (str):
            Path to the DOCX file.
        model_class (class):
            Django model into which the data will be imported.
        csv_column_count (int):
            Number of columns in the CSV file.
        mapping (dict, optional):
            Dictionary for mapping fields from the DOCX file to CSV columns.
            If not specified, fields are automatically assigned to columns.
        repeating_value (str, optional):
            Value for a specific column that repeats in each row of the final CSV.
            (Used to ensure that the column does not contain NULL values.)
            Defaults to None.
    """

    def __init__(self, docx_path, model_class, csv_column_count, mapping=None, repeating_value=None) -> None:
        logging.info("Initializing DocxToDB class")
        self.docx_document = Document(docx_path)
        self.model_class = model_class
        self.csv_column_count = csv_column_count
        self.mapping = mapping or {}
        self.document_csv = pd.DataFrame()
        self.csv_path = None
        self.repeating_value = repeating_value

    def docx_to_csv(self) -> None:
        logging.info(f"Start converting DOCX table to database for model {self.model_class.__name__}")
        logging.info("Converting DOCX table to CSV")
        self.model_class.objects.all().delete()

        try:
            with tempfile.NamedTemporaryFile(delete=False, mode='w', newline='', encoding='utf-8',
                                             suffix='.csv') as temp_file:
                self.csv_path = temp_file.name
                writer = csv.writer(temp_file, delimiter=';')

                for table in self.docx_document.tables:
                    for row in table.rows:
                        row_data = [cell.text.replace('\n', ' ').strip() for cell in row.cells]

                        if self.repeating_value is not None:
                            if row_data[self.repeating_value]:
                                last_value = row_data[self.repeating_value]
                            else:
                                row_data[self.repeating_value] = last_value

                        row_data = row_data[:self.csv_column_count]
                        while len(row_data) < self.csv_column_count:
                            row_data.append('')

                        writer.writerow(row_data)

            logging.info("DOCX successfully converted to CSV")
            self.document_csv = pd.read_csv(self.csv_path, delimiter=';')
            self.delete_duplicates()

        except Exception as e:
            logging.error(f"Error during DOCX to CSV conversion: {str(e)}")
            raise RuntimeError(f"Error converting DOCX to CSV: {str(e)}")

    def delete_duplicates(self) -> None:
        logging.info("Removing duplicate rows from CSV")
        self.document_csv.drop_duplicates(inplace=True)
        self.document_csv = self.document_csv.where(pd.notnull(self.document_csv), None)
        self.document_csv.to_csv(self.csv_path, index=False, encoding="utf-8", sep=';')
        logging.info("Duplicates removed, proceeding to database import")
        self.import_to_db()

    def import_to_db(self) -> None:
        try:
            logging.info("Starting data import to DB")
            csv_data = pd.read_csv(self.csv_path, delimiter=';', header=0)

            for _, row in csv_data.iterrows():
                row_data = {}
                for col_num, field_name in self.mapping.items():
                    if col_num < len(row):
                        value = row[col_num]
                        value = None if pd.isna(value) else value
                        row_data[field_name] = value

                if row_data:
                    self.model_class.objects.create(**row_data)

            logging.info("Data successfully imported into the database")
            self.cleanup()
        except Exception as e:
            logging.error(f"Error during database import: {str(e)}")
            raise RuntimeError(f"Error importing data into the database: {str(e)}")

    def cleanup(self) -> None:
        if self.csv_path:
            try:
                os.remove(self.csv_path)
                logging.info("Temporary CSV file deleted")
            except OSError as e:
                logging.error(f"Error deleting temporary file: {str(e)}")
                raise RuntimeError(f"Error deleting temporary file: {str(e)}")

# class ImportDocument402n(DocxToDB):
#     """
#     This class extends `DocxToDB` and provides a specific column mapping
#     for the 402n document format. It also includes additional parsing logic
#     before importing the data into the database.
#     """
#
#     def __init__(self, docx_path, model_class) -> None:
#         logging.info("Initializing ImportDocument402n class")
#         column_mapping = {
#             0: 'number_402n',
#             1: 'class_402n',
#             2: 'rubric_402n',
#             3: 'service_code_402n',
#             4: 'service_name_402n',
#             5: 'service_code_add_402n',
#             6: 'service_name_add_402n',
#         }
#         repeating_value = 0
#         super().__init__(docx_path, model_class, csv_column_count=7, mapping=column_mapping,
#                          repeating_value=repeating_value)
#
#     def import_to_db(self) -> None:
#         logging.info("Additional parsing CSV before import")
#         parser = MkbRubricsParser(input_file=self.csv_path, output_file='output.csv', row_table=2)
#         parser.parse()
#         logging.info("CSV parsed")
#         super().import_to_db()
