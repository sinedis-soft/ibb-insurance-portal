const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  return (
    <main className="shell">
      <section className="statusPanel">
        <p className="eyebrow">IBB Insurance Portal</p>
        <h1>Local MVP runtime</h1>
        <dl>
          <div>
            <dt>Frontend</dt>
            <dd>ready</dd>
          </div>
          <div>
            <dt>Backend API</dt>
            <dd>{apiBaseUrl}</dd>
          </div>
        </dl>
        <a href={`${apiBaseUrl}/health`} rel="noreferrer" target="_blank">
          Open backend health
        </a>
      </section>
    </main>
  );
}
