import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

/**
 * Render a DOM element to a PDF (§11.9, §12.7). The cloned document has its
 * `dark` class stripped, so exports are ALWAYS in light theme regardless of the
 * app theme — a printed artefact should look like paper.
 */
export async function exportElementToPdf(
  element: HTMLElement,
  filename: string,
  opts: { title?: string } = {},
): Promise<void> {
  const canvas = await html2canvas(element, {
    scale: 2,
    backgroundColor: '#ffffff',
    useCORS: true,
    logging: false,
    onclone: (doc) => {
      doc.documentElement.classList.remove('dark');
    },
  });

  const image = canvas.toDataURL('image/png');
  const pdf = new jsPDF({ unit: 'pt', format: 'a4', orientation: 'portrait' });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 32;

  let cursorY = margin;
  if (opts.title) {
    pdf.setFontSize(12);
    pdf.text(opts.title, margin, cursorY);
    cursorY += 16;
  }

  const imgWidth = pageWidth - margin * 2;
  const imgHeight = (canvas.height * imgWidth) / canvas.width;

  // Paginate tall content across pages.
  let remaining = imgHeight;
  let sourceY = 0;
  const usableHeight = pageHeight - cursorY - margin;

  if (imgHeight <= usableHeight) {
    pdf.addImage(image, 'PNG', margin, cursorY, imgWidth, imgHeight);
  } else {
    while (remaining > 0) {
      const sliceHeight = Math.min(usableHeight, remaining);
      pdf.addImage(image, 'PNG', margin, cursorY - sourceY, imgWidth, imgHeight);
      remaining -= sliceHeight;
      sourceY += sliceHeight;
      if (remaining > 0) {
        pdf.addPage();
        cursorY = margin;
      }
    }
  }

  pdf.save(filename.endsWith('.pdf') ? filename : `${filename}.pdf`);
}
