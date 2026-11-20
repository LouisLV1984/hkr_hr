"""PDF viewer, original-byte delivery and offline assets share existing file routes."""
import io
import unittest
from pathlib import Path
import test_v1_workflows as workflow
from models import db, AttendanceBatchItem, EmployeeDocument

class PdfPreviewTests(unittest.TestCase):
    setUp = workflow.V1WorkflowTests.setUp
    tearDown = workflow.V1WorkflowTests.tearDown
    login = workflow.V1WorkflowTests.login
    create_employee = workflow.V1WorkflowTests.create_employee

    def test_batch_and_employee_viewer_keep_original_bytes(self):
        content = workflow.pdf_bytes('Preview QA')
        self.client.post('/attendance/batches', data={'year_month':'2026-08', 'files':(io.BytesIO(content),'QA.pdf')}, content_type='multipart/form-data')
        eid, _ = self.create_employee('HKR', 'management', 'PDF測試', 'PDF QA')
        with self.app.app_context():
            item = AttendanceBatchItem.query.one()
            item_id = item.id
            item.batch.year_month = '2026-09'
            item.year_month = '2026-08'
            batch_id = item.batch_id
            doc = EmployeeDocument(employee_id=eid, category='general', original_filename='QA.PDF', stored_path=item.stored_path, mime_type='application/pdf', file_ext=None)
            db.session.add(doc); db.session.commit(); doc_id = doc.id
        collection = self.client.get(f'/attendance?view=collection&month=2026-11&batch_id={batch_id}').get_data(as_text=True)
        self.assertRegex(collection, r'<h2>2026年8月 · [^<]+1 PDF</h2>')
        self.assertNotIn('<strong>2026年9月 ·', collection)
        for url in (f'/attendance/items/{item_id}/open', f'/documents/{doc_id}/open'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('data-pdf-viewer', response.get_data(as_text=True))
            raw = self.client.get(url+'?raw=1')
            self.assertEqual(raw.mimetype, 'application/pdf')
            self.assertEqual(raw.data, content)
            raw.close()
            partial = self.client.get(url+'?raw=1', headers={'Range':'bytes=0-19'})
            self.assertEqual(partial.status_code,206)
            self.assertEqual(partial.data,content[:20]);partial.close()
        for url in (f'/attendance/items/{item_id}/open?download=1',f'/documents/{doc_id}/download'):
            response = self.client.get(url)
            self.assertIn('attachment',response.headers['Content-Disposition'])
            self.assertEqual(response.data,content);response.close()
        for path in ('js/pdf-preview.mjs','vendor/pdfjs/build/pdf.mjs','vendor/pdfjs/build/pdf.worker.mjs'):
            response = self.client.get('/static/'+path)
            self.assertEqual(response.status_code,200)
            self.assertIn(response.mimetype, ('text/javascript','application/javascript'))
            response.close()
        with self.app.app_context():
            self.assertEqual(AttendanceBatchItem.query.count(),1)
            self.assertEqual(EmployeeDocument.query.count(),1)

if __name__ == '__main__': unittest.main()
