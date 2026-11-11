/* A section the web console does not show yet: an honest notice, never demo data. */
import { useI18n } from "../i18n";
import { href } from "../navigation";

export function Placeholder({ section: key }: { section: string }) {
  const { t, section } = useI18n();
  return (
    <section className="panel connection-page empty" data-section={key}>
      <h1>{section(key)}</h1>
      <p>{t("Этот раздел ещё недоступен в веб-консоли")}</p>
      <div className="connection-page-actions">
        <a className="btn" href={href("")}>
          {section("Home")}
        </a>
      </div>
    </section>
  );
}
