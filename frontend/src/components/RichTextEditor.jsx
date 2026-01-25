import React from "react";

export default function RichTextEditor({ value, onChange }) {
  return (
    <div className="html-editor-split">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Enter HTML content here (e.g., <p>Description</p>, <b>Bold text</b>, <ul><li>List items</li></ul>)"
        className="html-editor"
      />
      <div className="html-preview-live">
        <div className="preview-label">Live Preview</div>
        <div
          className="preview-content"
          dangerouslySetInnerHTML={{ __html: value || "" }}
        />
      </div>
    </div>
  );
}
