const pdfBytes = label => {
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>'
  ];
  let text = '%PDF-1.4\n% ' + String(label).replace(/[^a-zA-Z0-9 ]/g, '') + '\n';
  const offsets = [0];
  for (let i=0; i<objects.length; i++) {
    offsets.push(Buffer.byteLength(text));
    text += `${i+1} 0 obj\n${objects[i]}\nendobj\n`;
  }
  const xref = Buffer.byteLength(text);
  text += 'xref\n0 4\n0000000000 65535 f \n' + offsets.slice(1).map(n=>String(n).padStart(10,'0')+' 00000 n \n').join('');
  text += `trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(text);
};
module.exports = {pdfBytes};
