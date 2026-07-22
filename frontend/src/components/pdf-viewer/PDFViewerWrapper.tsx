import dynamic from "next/dynamic";
import { type PDFViewerHandle } from "./PDFViewer";

const PDFViewerWrapper = dynamic(() => import("./PDFViewer"), {
  ssr: false,
  loading: () => (
    <div className="flex flex-col items-center justify-center h-full text-muted bg-preview">
      <div className="w-8 h-8 animate-spin rounded-full border-4 border-emerald border-t-transparent mb-4"></div>
      <p>Loading PDF Viewer...</p>
    </div>
  ),
});

export default PDFViewerWrapper;
