import { useMemo, useState } from 'react';

type WarningItem = {
  level: 'warning' | 'error' | 'info' | 'success';
  field: string;
  message: string;
};

type ExtractedRow = {
  date: string;
  description: string;
  debit: string;
  credit: string;
  balance: string;
};

type InvoiceLineItem = {
  description: string;
  hsn_code: string;
  quantity: string;
  unit: string;
  rate: string;
  amount: string;
};

type ExtractResponse = {
  document_type: 'invoice' | 'ledger' | 'unknown';
  raw_text: string;
  fields: Record<string, string>;
  rows: ExtractedRow[];
  line_items: InvoiceLineItem[];
  warnings: WarningItem[];
  confidence: {
    overall: number;
  };
};

const API_BASE = 'http://127.0.0.1:8000';

const invoiceSampleClean: ExtractResponse = {
  document_type: 'invoice',
  raw_text: 'ABC Traders\nGSTIN: 27ABCDE1234F1Z5\nInvoice No: INV-102\nDate: 12/04/2025\nTaxable Amount: 10000\nCGST: 900\nSGST: 900\nTotal: 11800',
  fields: {
    gstin: '27ABCDE1234F1Z5',
    buyer_gstin: '07ABCDE5678K1Z4',
    invoice_number: 'INV-102',
    date: '12/04/2025',
    vendor_name: 'ABC Traders',
    buyer_name: 'Rahul Enterprises',
    taxable_amount: '10000',
    cgst: '900',
    sgst: '900',
    igst: '0',
    total: '11800',
  },
  rows: [],
  line_items: [
    { description: 'Widget A', hsn_code: '8401', quantity: '10', unit: 'pcs', rate: '500', amount: '5000' },
    { description: 'Widget B', hsn_code: '8402', quantity: '5', unit: 'pcs', rate: '1000', amount: '5000' }
  ],
  warnings: [
    { level: 'success', field: 'total', message: 'Math validated: 10000 + 900 + 900 + 0 = 11800 (total: 11800)' },
    { level: 'success', field: 'gstin', message: 'Supplier GSTIN verified: 27ABCDE1234F1Z5' },
    { level: 'success', field: 'buyer_gstin', message: 'Buyer GSTIN found: 07ABCDE5678K1Z4' },
    { level: 'success', field: 'line_items', message: '2 line item(s) extracted with HSN codes.' }
  ],
  confidence: { overall: 0.98 },
};

const receiptSample: ExtractResponse = {
  document_type: 'invoice',
  raw_text: 'Coffee Shop\nDate: 04-Oct-2025\nAmount: 450\nTax: 22.5\nTotal: 472.5',
  fields: {
    vendor_name: 'Coffee Shop',
    date: '04-Oct-2025',
    taxable_amount: '450',
    cgst: '22.5',
    total: '472.5'
  },
  rows: [],
  line_items: [],
  warnings: [
    { level: 'warning', field: 'gstin', message: 'Supplier GSTIN is missing.' },
    { level: 'warning', field: 'buyer_gstin', message: 'Buyer GSTIN is missing. ITC claims require both GSTINs.' },
    { level: 'info', field: 'line_items', message: 'No line items extracted. HSN codes may be missing from the scan.' }
  ],
  confidence: { overall: 0.72 },
};

const passbookSample: ExtractResponse = {
  document_type: 'ledger',
  raw_text: '12/04/2025 UPI CREDIT FROM RAHUL 5000 21500\n13/04/2025 ATM WITHDRAWAL 2000 19500',
  fields: {},
  rows: [
    { date: '12/04/2025', description: 'UPI CREDIT FROM RAHUL', debit: '', credit: '5000', balance: '21500' },
    { date: '13/04/2025', description: 'ATM WITHDRAWAL', debit: '2000', credit: '', balance: '19500' },
  ],
  line_items: [],
  warnings: [
    { level: 'success', field: 'ledger', message: 'All 2 transaction(s) validated. Balances are consistent.' },
  ],
  confidence: { overall: 0.9 },
};

const emptyResponse: ExtractResponse = {
  document_type: 'unknown',
  raw_text: '',
  fields: {},
  rows: [],
  line_items: [],
  warnings: [],
  confidence: { overall: 0 },
};

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [response, setResponse] = useState<ExtractResponse>(emptyResponse);
  const [status, setStatus] = useState<'idle' | 'processing' | 'done' | 'error'>('idle');
  const [error, setError] = useState('');
  const [templateId, setTemplateId] = useState('');

  const fieldEntries = useMemo(() => Object.entries(response.fields), [response.fields]);

  const setSample = (sample: ExtractResponse) => {
    setResponse(sample);
    setStatus('done');
    setError('');
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setError('');
    setStatus('idle');
    setResponse(emptyResponse);

    if (selected) {
      const objectUrl = URL.createObjectURL(selected);
      setPreviewUrl(objectUrl);
    } else {
      setPreviewUrl('');
    }
  };

  const runExtraction = async () => {
    if (!file) {
      setError('Select an image first.');
      setStatus('error');
      return;
    }

    setStatus('processing');
    setError('');

    const formData = new FormData();
    formData.append('file', file);
    if (templateId.trim()) {
      formData.append('template_id', templateId.trim());
    }

    try {
      const result = await fetch(`${API_BASE}/api/extract`, {
        method: 'POST',
        body: formData,
      });

      if (!result.ok) {
        throw new Error(`Extraction failed with status ${result.status}`);
      }

      const data = (await result.json()) as ExtractResponse;
      setResponse(data);
      setStatus('done');
    } catch (fetchError) {
      setStatus('error');
      setError(fetchError instanceof Error ? fetchError.message : 'Unknown error');
    }
  };

  const downloadCsv = async () => {
    try {
      const result = await fetch(`${API_BASE}/api/export/csv`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(response),
      });

      if (!result.ok) {
        throw new Error(`CSV export failed with status ${result.status}`);
      }

      const blob = await result.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'scan2sheet-export.csv';
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (fetchError) {
      setStatus('error');
      setError(fetchError instanceof Error ? fetchError.message : 'Unknown error');
    }
  };

  const downloadTallyXml = async () => {
    try {
      const result = await fetch(`${API_BASE}/api/export/tally`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(response),
      });

      if (!result.ok) {
        throw new Error(`Tally XML export failed with status ${result.status}`);
      }

      const blob = await result.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'scan2sheet-tally.xml';
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (fetchError) {
      setStatus('error');
      setError(fetchError instanceof Error ? fetchError.message : 'Unknown error');
    }
  };

  const updateField = (fieldName: string, value: string) => {
    setResponse((current) => ({
      ...current,
      fields: {
        ...current.fields,
        [fieldName]: value,
      },
    }));
  };

  const updateRow = (rowIndex: number, key: keyof ExtractedRow, value: string) => {
    setResponse((current) => ({
      ...current,
      rows: current.rows.map((row, index) => (index === rowIndex ? { ...row, [key]: value } : row)),
    }));
  };

  const addLedgerRow = () => {
    setResponse((current) => ({
      ...current,
      rows: [
        ...current.rows,
        { date: '', description: '', debit: '', credit: '', balance: '' },
      ],
    }));
  };

  const removeRow = (rowIndex: number) => {
    setResponse((current) => ({
      ...current,
      rows: current.rows.filter((_, index) => index !== rowIndex),
    }));
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Verified OCR for Indian accounting workflows</p>
          <h1>Scan2Sheet Local</h1>
        </div>
        <div className={`badge badge-${response.document_type}`}>{response.document_type}</div>
      </header>

      <main className="layout">
        <section className="panel">
          <h2>Input Document</h2>
          <div className="button-row wrap">
            <button onClick={() => setSample(invoiceSampleClean)}>Try Sample GST Invoice (Clean)</button>
            <button onClick={() => setSample(receiptSample)}>Try Sample Receipt (Crumpled/Thermal)</button>
            <button onClick={() => setSample(passbookSample)}>Try Sample Bank Passbook (Multi-row)</button>
          </div>
          
          <input type="file" accept="image/*,application/pdf,.csv,.xls,.xlsx" onChange={handleFileChange} />
          
          <div style={{ margin: '24px 0 0' }}>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '8px' }}>Template ID (Optional)</label>
            <input 
              type="text" 
              placeholder="Leave blank for automatic extraction" 
              value={templateId} 
              onChange={(e) => setTemplateId(e.target.value)} 
            />
          </div>

          <button className="btn-stamp" onClick={runExtraction} disabled={status === 'processing' || !file && status !== 'done'}>
            {status === 'processing' ? 'Extracting...' : 'Extract Data'}
          </button>

          {previewUrl && file?.type.startsWith('image/') ? <img className="preview" src={previewUrl} alt="Document preview" /> : <div className="placeholder">{file ? file.name : "Select a document to view"}</div>}
          
          <p className="status-line">Status: {status}</p>
          {error ? <p className="error">{error}</p> : null}
          <p className="muted">Backend: {API_BASE}</p>
        </section>

        <section className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--text)', paddingBottom: '0.5rem', marginBottom: '1.5rem' }}>
            <h2 style={{ borderBottom: 'none', margin: 0, padding: 0 }}>Review Data</h2>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button onClick={downloadCsv} disabled={status !== 'done'}>Export CSV</button>
              <button onClick={downloadTallyXml} disabled={status !== 'done'} style={{ background: '#D43A2C', color: '#F4F4F1', borderColor: '#D43A2C' }}>Export Tally XML</button>
            </div>
          </div>
          
          <div className="metric">Confidence: {(response.confidence.overall * 100).toFixed(2)}%</div>

          <h3>Validation</h3>
          {response.warnings.length ? (
            <div className="validation-list" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {response.warnings.map((warning, index) => (
                <div key={`${warning.message}-${index}`} style={{
                  padding: '12px 16px',
                  borderRadius: '6px',
                  backgroundColor: warning.level === 'success' ? '#EDF7ED' :
                                 warning.level === 'warning' ? '#FFF4E5' :
                                 warning.level === 'error' ? '#FDEDED' : '#F5F5F5',
                  color: warning.level === 'success' ? '#1E4620' :
                         warning.level === 'warning' ? '#663C00' :
                         warning.level === 'error' ? '#5F2120' : '#333333',
                  border: `1px solid ${
                         warning.level === 'success' ? '#C8E6C9' :
                         warning.level === 'warning' ? '#FFE0B2' :
                         warning.level === 'error' ? '#FFCDD2' : '#E0E0E0'
                  }`,
                  display: 'flex',
                  alignItems: 'center',
                  fontWeight: 500,
                  fontSize: '0.95rem'
                }}>
                  <span style={{ marginRight: '12px', fontSize: '1.4rem' }}>
                    {warning.level === 'success' ? '✓' : warning.level === 'warning' ? '⚠️' : warning.level === 'error' ? '❌' : 'ℹ️'}
                  </span>
                  <div>
                    {warning.field ? <strong style={{ textTransform: 'capitalize' }}>{warning.field}: </strong> : ''}
                    {warning.message}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">Validation results appear after extraction.</p>
          )}

          <h3>Fields</h3>
          {fieldEntries.length ? (
            <div className="table">
              {fieldEntries.map(([key, value]) => (
                <div className="table-row" key={key}>
                  <label>{key}</label>
                  <input value={value} onChange={(event) => updateField(key, event.target.value)} />
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">No structured fields yet.</p>
          )}

          {response.line_items.length > 0 && (
            <>
              <h3>Line Items</h3>
              <div className="rows">
                <div className="row-card" style={{ fontWeight: 600, fontSize: '0.85rem' }}>
                  <span style={{ padding: '12px' }}>Description</span>
                  <span style={{ padding: '12px' }}>HSN Code</span>
                  <span style={{ padding: '12px' }}>Qty</span>
                  <span style={{ padding: '12px' }}>Rate</span>
                  <span style={{ padding: '12px' }}>Amount</span>
                  <span></span>
                </div>
                {response.line_items.map((item, index) => (
                  <div className="row-card" key={`lineitem-${index}`}>
                    <input value={item.description} readOnly style={{ background: 'transparent' }} />
                    <input value={item.hsn_code} readOnly style={{ background: 'transparent' }} />
                    <input value={item.quantity} readOnly style={{ background: 'transparent' }} />
                    <input value={item.rate} readOnly style={{ background: 'transparent' }} />
                    <input value={item.amount} readOnly style={{ background: 'transparent' }} />
                    <span style={{ padding: '12px', color: '#8C8C85', fontSize: '0.8rem' }}>{item.unit}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          <h3>Ledger Rows</h3>
          {response.document_type === 'ledger' ? (
            <>
              <div className="button-row">
                <button onClick={addLedgerRow}>Add Row</button>
              </div>
              {response.rows.length ? (
                <div className="rows">
                  {response.rows.map((row, index) => (
                    <div className="row-card" key={`${row.date}-${index}`}>
                      <input value={row.date} placeholder="Date" onChange={(event) => updateRow(index, 'date', event.target.value)} />
                      <input value={row.description} placeholder="Description" onChange={(event) => updateRow(index, 'description', event.target.value)} />
                      <input value={row.debit} placeholder="Debit" onChange={(event) => updateRow(index, 'debit', event.target.value)} />
                      <input value={row.credit} placeholder="Credit" onChange={(event) => updateRow(index, 'credit', event.target.value)} />
                      <input value={row.balance} placeholder="Balance" onChange={(event) => updateRow(index, 'balance', event.target.value)} />
                      <button className="delete-button" onClick={() => removeRow(index)}>Delete</button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">No transaction rows yet.</p>
              )}
            </>
          ) : (
            <p className="muted">Ledger rows appear when the document is classified as a ledger.</p>
          )}
        </section>
      </main>

      <section className="panel raw-panel">
        <h2>Raw OCR Text</h2>
        <pre>{response.raw_text || 'OCR text will appear here after extraction.'}</pre>
      </section>
    </div>
  );
}
