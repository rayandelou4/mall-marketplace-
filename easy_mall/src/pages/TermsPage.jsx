import React from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, CircleAlert, Scale } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { useTheme } from "../features/theme/ThemeContext";
import { cx } from "../styles/theme";

const SECTIONS = [
  { id: "service", title: "1. Le service Mall" },
  { id: "compte", title: "2. Votre compte" },
  { id: "annonces", title: "3. Annonces et vendeurs" },
  { id: "achats", title: "4. Achats et commandes" },
  { id: "remise", title: "5. Remise, livraison et services" },
  { id: "echanges", title: "6. Messages, avis et respect" },
  { id: "contenus", title: "7. Contenus, signalements et modération" },
  { id: "donnees", title: "8. Données et sécurité" },
  { id: "fin", title: "9. Disponibilité et évolution" },
];

function TermsSection({ id, title, t, children }) {
  return (
    <section id={id} className={cx("scroll-mt-24 border-b py-7 last:border-0", t.border)}>
      <h2 className={cx("text-lg font-semibold", t.textPrimary)}>{title}</h2>
      <div className={cx("mt-3 space-y-3 text-sm leading-6", t.textMuted)}>{children}</div>
    </section>
  );
}

export default function TermsPage() {
  const { t } = useTheme();

  return (
    <div className={cx("flex min-h-screen flex-col", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 lg:py-12">
        <header className={cx("border-b pb-7", t.border)}>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-indigo-600">
            <Scale className="h-4 w-4" aria-hidden="true" /> Informations légales
          </div>
          <h1 className={cx("mt-2 text-3xl font-semibold", t.textPrimary)}>Conditions d’utilisation</h1>
          <p className={cx("mt-3 max-w-3xl text-sm leading-6", t.textMuted)}>
            Ces règles expliquent comment utiliser Mall pour publier, acheter, vendre et échanger. En créant un compte ou en utilisant le service, vous acceptez de les respecter.
          </p>
        </header>

        <div className="grid gap-8 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-14">
          <nav aria-label="Sommaire des conditions" className="lg:sticky lg:top-24 lg:h-fit lg:py-8">
            <p className={cx("mb-3 text-xs font-semibold uppercase", t.textMuted)}>Sommaire</p>
            <ul className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible">
              {SECTIONS.map((section) => (
                <li key={section.id} className="shrink-0">
                  <a href={`#${section.id}`} className={cx("block rounded-lg px-3 py-2 text-sm hover:bg-indigo-50 hover:text-indigo-700 dark:hover:bg-indigo-950 dark:hover:text-indigo-300", t.textMuted)}>
                    {section.title}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <article className="min-w-0">
            <TermsSection id="service" title="1. Le service Mall" t={t}>
              <p>Mall met en relation des acheteurs et des vendeurs, particuliers ou professionnels. Le site permet de publier des annonces de produits et de services, d’échanger par messagerie, de passer des commandes de produits et d’en suivre l’état.</p>
              <p>Sauf indication contraire affichée au moment de la commande, le contrat de vente ou de prestation est conclu directement entre l’acheteur et le vendeur. Mall n’est pas propriétaire des articles, ne réalise pas les prestations et n’organise pas lui-même leur remise ou leur livraison.</p>
            </TermsSection>

            <TermsSection id="compte" title="2. Votre compte" t={t}>
              <p>Pour créer un compte, fournissez une adresse e-mail, un numéro de téléphone et un nom d’utilisateur valides, ainsi que les autres informations demandées. Vous devez confirmer votre adresse e-mail pour activer le compte et accéder aux fonctions qui le nécessitent.</p>
              <p>Vous êtes responsable de l’exactitude des informations fournies, de la confidentialité de vos identifiants et des activités réalisées depuis votre compte. Signalez-nous sans délai tout accès que vous ne reconnaissez pas. Vous pouvez utiliser le même compte pour acheter et vendre.</p>
              <p>Les badges de vérification décrivent les vérifications indiquées sur le profil. Un e-mail vérifié ne prouve pas une identité; les autres badges ne garantissent ni l’authenticité d’un document, ni la qualité d’un article, ni la réussite d’une transaction.</p>
            </TermsSection>

            <TermsSection id="annonces" title="3. Annonces et vendeurs" t={t}>
              <p>Le vendeur est responsable de ses annonces, de ses produits ou services et des informations publiées: description, état, disponibilité, quantité, prix, devise, lieu, frais de livraison et conditions de remise. Les informations doivent être exactes, à jour et suffisamment claires pour éviter toute confusion.</p>
              <p>Ne publiez que des contenus que vous êtes autorisé à utiliser. Les annonces trompeuses, les prix mensongers, les produits contrefaits ou interdits, les tentatives d’arnaque et les contenus qui enfreignent les droits d’autrui ne sont pas autorisés. Respectez également les lois applicables à votre activité et aux produits ou services proposés.</p>
              <p>Une annonce peut être examinée avant ou après sa publication. Mall peut la masquer, la suspendre ou la retirer lorsqu’un examen ou un signalement le justifie, notamment si elle semble enfreindre ces règles ou la loi. Le vendeur doit maintenir son stock et ses modalités à jour; une annonce publiée peut devenir indisponible.</p>
            </TermsSection>

            <TermsSection id="achats" title="4. Achats et commandes" t={t}>
              <p>Le panier et la commande concernent les produits disponibles; les services se réservent en contactant directement le prestataire. Avant de confirmer une commande, vérifiez les articles, quantités, prix, devise et frais de livraison. Les articles d’une même commande doivent être dans la même devise.</p>
              <p>La commande est vérifiée selon la disponibilité, le stock et le prix au moment de sa création. Si le prix, les frais ou le stock ont changé, la commande peut être refusée et le panier devra être actualisé. L’enregistrement d’une commande ne signifie pas que le paiement a été effectué.</p>
              <p>Le paiement proposé actuellement est en espèces, directement au vendeur lors de la remise. Mall n’encaisse pas ce paiement. Les moyens de paiement affichés comme indisponibles, notamment Mobile Money, ne peuvent pas être utilisés sur le site.</p>
              <p>L’acheteur peut annuler une commande depuis son compte tant qu’elle est en attente et qu’aucune expédition n’a commencé. Après cette étape, utilisez la messagerie pour contacter le vendeur ou signalez un litige si nécessaire.</p>
            </TermsSection>

            <TermsSection id="remise" title="5. Remise, livraison et services" t={t}>
              <p>Le mode proposé est précisé dans l’annonce. L’acheteur et le vendeur conviennent des détails pratiques par messagerie. Pour une livraison, le vendeur en organise les modalités; pour une remise en main propre, les deux parties conviennent du lieu et du moment. Vérifiez l’article ou la prestation et réglez le vendeur au moment convenu.</p>
              <p>Une adresse de livraison n’est demandée que lorsqu’elle est nécessaire à la commande. Fournissez des informations exactes et utilisez-les uniquement pour cette commande. Les parties autorisées à la traiter peuvent y accéder afin d’organiser la livraison.</p>
              <p>Une annonce de service n’est pas achetable dans le panier. Avant toute réservation, convenez directement avec le prestataire du contenu de la prestation, du tarif, des disponibilités, du lieu et des modalités de paiement.</p>
            </TermsSection>

            <TermsSection id="echanges" title="6. Messages, avis et respect" t={t}>
              <p>Utilisez les messages pour échanger au sujet des annonces, commandes et prestations. Les menaces, le harcèlement, les sollicitations frauduleuses, le partage abusif de données personnelles et les messages illégaux sont interdits. Vous pouvez signaler un message depuis ses options.</p>
              <p>Un acheteur peut laisser un avis après avoir confirmé la réception d’une commande. Les avis doivent être sincères, liés à l’expérience vécue et rédigés sans menace ni contrepartie trompeuse. Un avis peut être examiné et ne constitue pas une garantie sur les transactions futures.</p>
            </TermsSection>

            <TermsSection id="contenus" title="7. Contenus, signalements et modération" t={t}>
              <p>Vous conservez la responsabilité des textes, images, messages, avis et autres contenus que vous publiez. Vous confirmez disposer des droits nécessaires pour les partager et ne pas porter atteinte aux droits d’une autre personne.</p>
              <p>Vous pouvez signaler une annonce depuis sa page, un message depuis ses options ou un problème de commande depuis « Mes commandes ». Les signalements sont examinés par l’équipe de modération; leur envoi ne garantit pas une décision particulière ni un délai de traitement déterminé.</p>
              <p>Pour protéger les utilisateurs et le service, Mall peut examiner les contenus signalés, demander des précisions, limiter temporairement leur visibilité, retirer une annonce ou restreindre un compte en cas de violation. Lorsque c’est possible, la décision est communiquée dans les notifications du compte.</p>
            </TermsSection>

            <TermsSection id="donnees" title="8. Données et sécurité" t={t}>
              <p>Le fonctionnement du compte, des annonces, des commandes et des messages nécessite le traitement de certaines informations. Les informations publiques du profil ou des annonces peuvent être visibles par les autres utilisateurs. Les adresses de livraison sont des informations privées utilisées pour traiter la commande.</p>
              <p>Ne partagez dans les annonces ou les messages que les renseignements nécessaires à l’échange. Protégez vos identifiants et restez vigilant face aux demandes de paiement anticipé ou de données sensibles qui ne sont pas nécessaires à la transaction.</p>
            </TermsSection>

            <TermsSection id="fin" title="9. Disponibilité et évolution" t={t}>
              <p>Mall peut faire évoluer le site, ses fonctions et les présentes conditions. Les changements importants seront signalés sur le site ou dans le compte lorsque cela est possible. L’utilisation du service après leur entrée en vigueur vaut acceptation des conditions mises à jour; si vous ne les acceptez pas, cessez d’utiliser les fonctions concernées.</p>
              <p>Le site peut être temporairement indisponible pour maintenance ou en raison d’un incident. Les outils de messagerie, d’avis, de vérification et de signalement aident les utilisateurs, mais ne remplacent pas leur vigilance ni les droits prévus par la loi.</p>
            </TermsSection>

            <aside className={cx("mt-6 flex gap-3 border-l-2 border-amber-400 py-2 pl-4 text-sm leading-6", t.textMuted)}>
              <CircleAlert className="mt-1 h-4 w-4 shrink-0 text-amber-600" aria-hidden="true" />
              <p>Avant publication officielle, ces conditions doivent être complétées avec l’identité légale et les coordonnées de l’exploitant de Mall, ainsi qu’avec les mentions et règles applicables dans les pays desservis. Elles ne remplacent pas un examen juridique local.</p>
            </aside>

            <p className={cx("mt-6 text-sm", t.textMuted)}>
              Besoin d’un repère sur les parcours du site ? <Link to="/aide" className="font-semibold text-indigo-600 hover:underline">Consulter le centre d’aide <ArrowUpRight className="inline h-4 w-4" /></Link>
            </p>
          </article>
        </div>
      </main>

      <SiteFooter t={t} />
    </div>
  );
}