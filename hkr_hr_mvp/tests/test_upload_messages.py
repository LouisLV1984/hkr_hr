"""Synthetic upload compatibility and safety regression fixtures."""
import io
import unittest
from unittest.mock import patch
from PIL import Image

from werkzeug.datastructures import FileStorage
from tools.security import validate_uploaded_file, UploadValidationError
from tools.i18n import TRANSLATIONS
import test_profile_workspace as workspace
from models import db, EmployeeAnnualLeaveRecord


def image_bytes(fmt="JPEG"):
    stream = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(stream, format=fmt)
    return stream.getvalue()


class UploadMessageTests(unittest.TestCase):
    def test_readable_jpeg_trailing_metadata_preserves_original_and_cursor(self):
        content = image_bytes() + bytes(range(24))
        for filename in ('photo.JPG', 'photo.jpeg'):
            stream = io.BytesIO(content)
            stream.seek(7)
            result = validate_uploaded_file(FileStorage(stream=stream, filename=filename))
            self.assertEqual(result['mime_type'], 'image/jpeg')
            self.assertEqual(result['size'], len(content))
            self.assertEqual(stream.tell(), 7)
            self.assertFalse(stream.closed)
            self.assertEqual(stream.getvalue(), content)

    def test_valid_png_and_jpeg(self):
        for fmt, name in [('JPEG', 'a.jpg'), ('PNG', 'a.PNG')]:
            self.assertGreater(validate_uploaded_file(FileStorage(
                stream=io.BytesIO(image_bytes(fmt)), filename=name))['size'], 0)

    def test_invalid_image_contents_still_rejected(self):
        for name, data in [('a.jpg', b'\xff\xd8\xffFAKE\xff\xd9'),
                           ('a.png', b'\x89PNG\r\n\x1a\nFAKE'),
                           ('a.jpg', image_bytes('PNG')),
                           ('a.png', image_bytes()),
                           ('a.jpg', image_bytes()[:-30])]:
            with self.subTest(name=name, size=len(data)):
                stream = io.BytesIO(data)
                stream.seek(2)
                with self.assertRaises(UploadValidationError):
                    validate_uploaded_file(FileStorage(stream=stream, filename=name))
                self.assertEqual(stream.tell(), 2)

    def test_image_pixel_limit_remains_enabled(self):
        with patch('tools.security.Image.open') as opened:
            opened.return_value.__enter__.return_value.width = 10000
            opened.return_value.__enter__.return_value.height = 10000
            with self.assertRaisesRegex(UploadValidationError, 'upload.image_too_large'):
                validate_uploaded_file(FileStorage(stream=io.BytesIO(image_bytes()), filename='a.jpg'))

    def test_validation_reasons_and_pdf_only_scope(self):
        cases = [
            ('a.heic', b'unknown', None, 'upload.unsupported_type'),
            ('a.jpg', b'unknown', {'.pdf'}, 'upload.pdf_only'),
            ('a.pdf', b'unknown', {'.pdf'}, 'upload.invalid_pdf'),
            ('a.jpg', b'unknown', None, 'upload.invalid_file'),
            ('a.pdf', b'', None, 'upload.empty_file'),
        ]
        for name, content, allowed, key in cases:
            with self.subTest(name=name, key=key):
                upload = FileStorage(stream=io.BytesIO(content), filename=name)
                with self.assertRaises(UploadValidationError) as raised:
                    validate_uploaded_file(upload, allowed)
                self.assertEqual(str(raised.exception), key)

    def test_all_languages_have_explicit_extensions_and_request_limit(self):
        for language, copy in TRANSLATIONS.items():
            for key in ('upload.unsupported_type', 'upload.invalid_file'):
                for extension in ('.pdf', '.jpg', '.jpeg', '.png', '.docx', '.xlsx'):
                    self.assertIn(extension, copy[key], (language, key))
            self.assertIn('.pdf', copy['upload.pdf_only'])
            self.assertNotIn('.jpg', copy['upload.invalid_pdf'])
            self.assertIn('32 MB', copy['error.413.message'])


class UploadErrorPageTests(unittest.TestCase):
    setUp = workspace.ProfileWorkspaceTests.setUp
    tearDown = workspace.ProfileWorkspaceTests.tearDown
    login = workspace.ProfileWorkspaceTests.login
    create_employee = workspace.ProfileWorkspaceTests.create_employee
    def employee(self):
        from datetime import date
        from models import EmployeeAssignment
        from tools.hr_core import reference_by_code
        eid = workspace.ProfileWorkspaceTests.employee(self)
        with self.app.app_context():
            db.session.add(EmployeeAssignment(employee_id=eid, effective_from=date(2026, 1, 1),
                payroll_group="management", workweek_days=5,
                region_id=reference_by_code("work_region", "HK").id))
            db.session.commit()
        return eid

    def test_leave_workspace_has_same_editor_error_recovery(self):
        eid = self.employee()
        response = self.client.get(f'/annual-leave?employee_id={eid}&year=2026')
        self.assertIn('data-profile-workspace', response.get_data(as_text=True))

    def test_sick_evidence_jpeg_metadata_saves_original_once(self):
        from models import EmployeeDocument
        from pathlib import Path
        eid = self.employee()
        data = image_bytes() + bytes(range(24))
        response = self.client.post(f'/employees/{eid}/annual-leave', data={
            'leave_type': 'sick', 'start_date': '2026-09-09', 'end_date': '2026-09-09',
            'start_session': 'am', 'end_session': 'pm',
            'evidence': (io.BytesIO(data), 'metadata.JPG'),
        }, headers={'X-HKR-Profile-Editor': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('redirect', response.json)
        with self.app.app_context():
            records = EmployeeAnnualLeaveRecord.query.filter_by(employee_id=eid).all()
            self.assertEqual(len(records), 1)
            doc = db.session.get(EmployeeDocument, records[0].evidence_document_id)
            self.assertEqual(Path(doc.stored_path).read_bytes(), data)

    def test_sick_evidence_error_has_readable_detail_and_does_not_create_leave(self):
        eid = self.employee()
        for name in ('invalid.jpg', 'unsupported.heic'):
            response = self.client.post(f'/employees/{eid}/annual-leave', data={
                'leave_type': 'sick', 'start_date': '2026-09-09', 'end_date': '2026-09-09',
                'start_session': 'am', 'end_session': 'pm',
                'evidence': (io.BytesIO(b'not an image'), name),
            }, headers={'X-HKR-Profile-Editor': '1'})
            self.assertEqual(response.status_code, 400)
            page = response.get_data(as_text=True)
            self.assertIn('data-error-detail', page)
            self.assertIn('.jpeg', page)
            self.assertIn('.xlsx', page)
        with self.app.app_context():
            self.assertEqual(EmployeeAnnualLeaveRecord.query.filter_by(employee_id=eid).count(), 0)
