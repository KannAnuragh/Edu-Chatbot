"use client";

import { useState, useRef } from "react";
import { UploadCloud, FileType, CheckCircle2, AlertCircle, X } from "lucide-react";
import { api } from "@/lib/api";
import { type Document } from "@/types";
import { cn } from "@/lib/utils";

interface UploadZoneProps {
  projectId: string;
  onUploadComplete?: (doc: Document) => void;
}

export default function UploadZone({ projectId, onUploadComplete }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      await handleFileUpload(files[0]);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await handleFileUpload(e.target.files[0]);
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleFileUpload = async (file: File) => {
    // Validate file
    setError(null);
    setSuccess(false);
    
    if (file.type !== "application/pdf") {
      setError("Only PDF files are allowed.");
      return;
    }
    
    if (file.size > 50 * 1024 * 1024) { // 50MB
      setError("File exceeds maximum size of 50MB.");
      return;
    }

    setUploading(true);
    setProgress(0);

    // Simulate progress while uploading
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) return prev;
        return prev + 10;
      });
    }, 200);

    try {
      const doc = await api.uploadDocument(projectId, file);
      clearInterval(progressInterval);
      setProgress(100);
      setSuccess(true);
      
      setTimeout(() => {
        setSuccess(false);
        setProgress(0);
        if (onUploadComplete) {
          onUploadComplete(doc);
        }
      }, 1000);
      
    } catch (err: any) {
      clearInterval(progressInterval);
      setProgress(0);
      setError(err.message || "Failed to upload document");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="w-full">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept="application/pdf"
        className="hidden"
      />

      <div
        onClick={() => !uploading && fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          "relative border-2 border-dashed rounded-xl p-6 transition-all text-center cursor-pointer overflow-hidden",
          isDragging ? "border-emerald bg-emerald-tint" : "border-border hover:border-emerald/50 hover:bg-rail",
          uploading ? "opacity-90 pointer-events-none" : ""
        )}
      >
        {/* Progress Bar Background */}
        {uploading && (
          <div 
            className="absolute bottom-0 left-0 h-1 bg-emerald transition-all duration-300 ease-out" 
            style={{ width: `${progress}%` }}
          />
        )}

        <div className="flex flex-col items-center justify-center gap-2">
          {success ? (
            <div className="w-10 h-10 rounded-full bg-emerald text-white flex items-center justify-center animate-bounce">
              <CheckCircle2 size={24} />
            </div>
          ) : uploading ? (
            <div className="w-10 h-10 rounded-full bg-emerald-tint text-emerald flex items-center justify-center animate-pulse border border-emerald-border">
              <UploadCloud size={20} />
            </div>
          ) : (
            <div className="w-10 h-10 rounded-full bg-rail text-muted flex items-center justify-center group-hover:bg-white group-hover:text-emerald transition-colors shadow-sm">
              <FileType size={20} />
            </div>
          )}

          <div className="mt-2">
            {success ? (
              <span className="text-sm font-medium text-emerald">Upload complete!</span>
            ) : uploading ? (
              <span className="text-sm font-medium text-emerald">Uploading... {progress}%</span>
            ) : (
              <>
                <p className="text-sm font-medium text-ink">
                  Click to upload <span className="text-muted font-normal">or drag and drop</span>
                </p>
                <p className="text-[11px] text-muted mt-1 font-mono">PDF files only (max 50MB)</p>
              </>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-3 flex items-start gap-2 text-[13px] text-red-600 bg-red-50 p-3 rounded-lg border border-red-100 animate-fade-in">
          <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
