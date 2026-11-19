import { getDocument, GlobalWorkerOptions } from '../vendor/pdfjs/build/pdf.mjs';
const assets = new URL('../vendor/pdfjs/', import.meta.url);
GlobalWorkerOptions.workerSrc = new URL('build/pdf.worker.mjs', assets).href;

for (const viewer of document.querySelectorAll('[data-pdf-viewer]')) {
  const viewport = viewer.querySelector('.pdf-viewport');
  const canvas = viewer.querySelector('[data-pdf-canvas]');
  const status = viewer.querySelector('[data-pdf-status]');
  const pageInput = viewer.querySelector('[data-pdf-page]');
  const prev = viewer.querySelector('[data-pdf-prev]');
  const next = viewer.querySelector('[data-pdf-next]');
  const zoom = viewer.querySelector('[data-pdf-zoom]');
  const rotate = viewer.querySelector('[data-pdf-rotate]');
  let pdf, pageNumber = 1, rotation = 0, rendering = false, pending = false;
  async function render() {
    if (!pdf) return;
    pending = true;
    if (rendering) return;
    rendering = true;
    while (pending) {
      pending = false;
      const requestedPage = pageNumber;
      status.hidden = false;
      status.textContent = viewer.dataset.loading;
      try {
        const page = await pdf.getPage(requestedPage);
        const base = page.getViewport({ scale: 1, rotation: (page.rotate + rotation) % 360 });
        const scale = zoom.value === 'fit' ? Math.max(0.1, (viewport.clientWidth - 24) / base.width) : Number(zoom.value);
        const size = page.getViewport({ scale, rotation: (page.rotate + rotation) % 360 });
        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.floor(size.width * ratio);
        canvas.height = Math.floor(size.height * ratio);
        canvas.style.width = size.width + 'px';
        canvas.style.height = size.height + 'px';
        await page.render({ canvasContext: canvas.getContext('2d'), viewport: size, transform: ratio === 1 ? null : [ratio, 0, 0, ratio, 0, 0] }).promise;
        canvas.hidden = false;
        canvas.dataset.renderedPage = String(requestedPage);
        status.hidden = true;
        page.cleanup();
      } catch (error) {
        canvas.hidden = true;
        status.textContent = viewer.dataset.error;
        console.error('PDF preview:', error);
      }
    }
    rendering = false;
    prev.disabled = pageNumber <= 1;
    next.disabled = pageNumber >= pdf.numPages;
  }
  function go(value) {
    pageNumber = Math.min(pdf.numPages, Math.max(1, Math.trunc(Number(value)) || 1));
    pageInput.value = pageNumber;
    viewport.scrollTop = 0;
    render();
  }
  prev.addEventListener('click', () => go(pageNumber - 1));
  next.addEventListener('click', () => go(pageNumber + 1));
  pageInput.addEventListener('change', () => go(pageInput.value));
  zoom.addEventListener('change', render);
  rotate.addEventListener('click', () => { rotation = (rotation + 90) % 360; render(); });
  let width = 0;
  new ResizeObserver(entries => {
    const nextWidth = Math.round(entries[0].contentRect.width);
    if (nextWidth !== width) { width = nextWidth; if (zoom.value === 'fit') render(); }
  }).observe(viewport);
  try {
    pdf = await getDocument({ url: viewer.dataset.source, cMapUrl: new URL('cmaps/', assets).href, cMapPacked: true, standardFontDataUrl: new URL('standard_fonts/', assets).href, wasmUrl: new URL('wasm/', assets).href }).promise;
    viewer.querySelector('[data-pdf-count]').textContent = '/ ' + pdf.numPages;
    pageInput.max = pdf.numPages;
    pageInput.disabled = zoom.disabled = rotate.disabled = false;
    await render();
  } catch (error) {
    status.textContent = viewer.dataset.error;
    console.error('PDF load:', error);
  }
}
