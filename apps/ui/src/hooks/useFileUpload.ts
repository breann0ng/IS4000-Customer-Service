import { useCallback, useState } from "react";

export interface FileAttachment {
  file: File;
  filename: string;
  fileType: string;
  extractedText: string;
  isImage: boolean;
  imageBase64: string | null;
  isUploading: boolean;
  error: string | null;
}

const ALLOWED_EXTENSIONS = new Set([
  "pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg", "gif", "webp",
]);

const MAX_FILE_SIZE_MB = 10;

function getExtension(filename: string): string {
  const parts = filename.split(".");
  return parts.length > 1 ? (parts.at(-1) ?? "").toLowerCase() : "";
}

export function useFileUpload() {
  const [attachment, setAttachment] = useState<FileAttachment | null>(null);

  const uploadFile = useCallback(async (file: File) => {
    const ext = getExtension(file.name);

    if (!ALLOWED_EXTENSIONS.has(ext)) {
      setAttachment({
        file,
        filename: file.name,
        fileType: ext,
        extractedText: "",
        isImage: false,
        imageBase64: null,
        isUploading: false,
        error: `Unsupported file type. Allowed: ${[...ALLOWED_EXTENSIONS].join(", ")}`,
      });
      return;
    }

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setAttachment({
        file,
        filename: file.name,
        fileType: ext,
        extractedText: "",
        isImage: false,
        imageBase64: null,
        isUploading: false,
        error: `File too large. Maximum size is ${MAX_FILE_SIZE_MB}MB.`,
      });
      return;
    }

    setAttachment({
      file,
      filename: file.name,
      fileType: ext,
      extractedText: "",
      isImage: false,
      imageBase64: null,
      isUploading: true,
      error: null,
    });

    try {
      const formData = new FormData();
      formData.append("file", file);

      const token = localStorage.getItem("access_token");
      const response = await fetch("/api/chat/upload", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(errorData.detail || "Upload failed");
      }

      const data = await response.json();
      setAttachment({
        file,
        filename: data.filename,
        fileType: data.file_type,
        extractedText: data.extracted_text,
        isImage: data.is_image,
        imageBase64: data.image_base64,
        isUploading: false,
        error: null,
      });
    } catch (err) {
      setAttachment((prev) =>
        prev ? { ...prev, isUploading: false, error: (err as Error).message } : null,
      );
    }
  }, []);

  const clearAttachment = useCallback(() => {
    setAttachment(null);
  }, []);

  return { attachment, uploadFile, clearAttachment };
}
