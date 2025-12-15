import { Component, ChangeDetectorRef, AfterViewInit, ViewChild, ElementRef, OnDestroy } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { MonacoEditorLanguageClientWrapper } from 'monaco-editor-wrapper';
import { createEditorConfig } from './configs/editor.config';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements AfterViewInit, OnDestroy {
  selectedFile: File | null = null;
  isConverting = false;
  convertedFiles: any[] = [];

  // Code strings for raw view
  originalCode = '';
  modifiedCode = '';

  downloadId: string | null = null;
  selectedFileName: string | null = null;
  errorMessage: string | null = null;
  showRawView = false; // Fallback toggle

  @ViewChild('originalContainer') originalContainer!: ElementRef;
  @ViewChild('modifiedContainer') modifiedContainer!: ElementRef;

  private originalWrapper = new MonacoEditorLanguageClientWrapper();
  private modifiedWrapper = new MonacoEditorLanguageClientWrapper();
  private editorsInitialized = false;

  constructor(private http: HttpClient, private cdr: ChangeDetectorRef) { }

  async ngAfterViewInit() {
    // Initial setup if needed, but we often wait for content to init
    // For specific requirement, we can init with empty content
    // However, wrappers need the container to be in DOM. 
    // Since we use *ngIf="!showRawView && convertedFiles.length > 0", container might not exist yet.
    // We will handle init in onFileSelect or use a setter/lifecycle check.
  }

  ngOnDestroy() {
    this.disposeEditors();
  }

  async disposeEditors() {
    try {
      await this.originalWrapper.dispose();
      await this.modifiedWrapper.dispose();
      this.editorsInitialized = false;
    } catch (e) {
      console.warn('Dispose error', e);
    }
  }

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0];
    this.selectedFileName = this.selectedFile ? this.selectedFile.name : null;
    this.convertedFiles = [];
    this.downloadId = null;
    this.downloadId = null;
    this.originalCode = '';
    this.modifiedCode = '';
    this.errorMessage = null;
    this.disposeEditors(); // Reset editors on new file
  }

  async convertProject() {
    if (!this.selectedFile) return;

    this.isConverting = true;
    this.convertedFiles = [];
    this.downloadId = null;
    this.errorMessage = null;

    const formData = new FormData();
    formData.append('file', this.selectedFile);

    try {
      const response = await fetch('http://localhost:5000/api/convert-stream', {
        method: 'POST',
        body: formData
      });

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const result = JSON.parse(line);
              this.handleStreamMessage(result);
            } catch (e) {
              console.error('Error parsing JSON line:', e);
            }
          }
        }

        if (done) break;
      }

      if (buffer.trim()) {
        try {
          const result = JSON.parse(buffer);
          this.handleStreamMessage(result);
        } catch (e) { }
      }

    } catch (error) {
      console.error('Conversion failed:', error);
      this.errorMessage = 'Connection failed. Is the backend running?';
    } finally {
      this.isConverting = false;
      this.cdr.detectChanges();
    }
  }

  handleStreamMessage(msg: any) {
    if (msg.type === 'file') {
      this.convertedFiles.push(msg.data);

      if (this.convertedFiles.length === 1) {
        this.onFileSelect(msg.data);
      }
      this.cdr.detectChanges();

    } else if (msg.type === 'complete') {
      this.downloadId = msg.downloadId;
      this.cdr.detectChanges();
    } else if (msg.type === 'error') {
      console.error('Stream error:', msg.message);
    }
  }

  async onFileSelect(file: any) {
    console.log('File selected:', file);

    // Update raw strings
    this.originalCode = file.originalCode || '';
    this.modifiedCode = file.convertedCode || '';

    // Fallback: If raw view is active, standard editors are hidden
    if (this.showRawView) return;

    // Wait for Change Detection so that *ngIf elements are rendered
    this.cdr.detectChanges();

    // Initialize or Update Editors
    if (!this.editorsInitialized && this.originalContainer && this.modifiedContainer) {
      await this.initEditors();
    } else if (this.editorsInitialized) {
      await this.updateEditorContent();
    }
  }

  async initEditors() {
    if (this.editorsInitialized) return;

    try {
      const origConfig = createEditorConfig(this.originalCode, 'csharp');
      const modConfig = createEditorConfig(this.modifiedCode, 'java');

      await this.originalWrapper.initAndStart(origConfig, this.originalContainer.nativeElement);
      await this.modifiedWrapper.initAndStart(modConfig, this.modifiedContainer.nativeElement);

      this.editorsInitialized = true;
    } catch (e) {
      console.error('Editor init failed:', e);
    }
  }

  async updateEditorContent() {
    try {
      const origEditor = this.originalWrapper.getEditor();
      if (origEditor) origEditor.setValue(this.originalCode);

      const modEditor = this.modifiedWrapper.getEditor();
      if (modEditor) modEditor.setValue(this.modifiedCode);
    } catch (e) {
      console.error('Editor update failed:', e);
      // Try re-init if update fails (e.g. if disposed unexpectedly)
      this.disposeEditors();
      this.initEditors();
    }
  }

  downloadZip() {
    if (!this.downloadId) return;
    window.location.href = `http://localhost:5000/api/download/${this.downloadId}`;
  }
}