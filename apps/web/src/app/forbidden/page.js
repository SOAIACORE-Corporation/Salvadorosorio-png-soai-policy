export default function ForbiddenPage() {
  return (
    <section className="auth-page">
      <p className="eyebrow">Access denied</p>
      <h1>Your operator role does not permit this action.</h1>
      <p>Contact the pilot administrator if your assigned role is incorrect.</p>
      <form action="/api/auth/logout" method="post">
        <button className="button" type="submit">Sign out</button>
      </form>
    </section>
  );
}
