import { useState, useCallback, useEffect } from "react";
import { useParams } from "react-router-dom";
import { apiBase } from "@/config";

interface TranscriptResponse {
  transcript: string;
  word_count: number;
}

export function useTranscript() {
  const { uuid } = useParams<{ uuid: string }>();
  const [transcript, setTranscript] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchTranscript = useCallback(async (signal?: AbortSignal) => {
    if (!uuid) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/projects/${uuid}/transcript`, {
        signal,
      });
      if (!response.ok) {
        if (response.status === 404) {
          setTranscript("");
          return;
        }
        throw new Error(`Failed to fetch transcript: ${response.status}`);
      }
      const data = (await response.json()) as TranscriptResponse;
      setTranscript(data.transcript || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [uuid]);

  useEffect(() => {
    const controller = new AbortController();
    fetchTranscript(controller.signal);
    return () => controller.abort();
  }, [fetchTranscript]);

  const handleUpload = useCallback(
    (file: File) => {
      if (!uuid) return;
      setUploading(true);
      setUploadProgress(0);
      setError(null);

      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append("file", file);

      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) {
          setUploadProgress(Math.round((event.loaded / event.total) * 100));
        }
      });

      xhr.addEventListener("load", () => {
        setUploading(false);
        if (xhr.status >= 200 && xhr.status < 300) {
          setUploadProgress(100);
          fetchTranscript();
        } else {
          setUploadProgress(0);
          setError(`Upload failed: ${xhr.status}`);
        }
      });

      xhr.addEventListener("error", () => {
        setUploading(false);
        setUploadProgress(0);
        setError("Upload failed");
      });

      xhr.addEventListener("abort", () => {
        setUploading(false);
        setUploadProgress(0);
        setError("Upload aborted");
      });

      xhr.open("POST", `${apiBase}/projects/${uuid}/voiceover`);
      xhr.send(formData);
    },
    [uuid, fetchTranscript]
  );

  return {
    transcript,
    fetchTranscript,
    handleUpload,
    loading,
    error,
    setError,
    uploading,
    uploadProgress,
  };
}
