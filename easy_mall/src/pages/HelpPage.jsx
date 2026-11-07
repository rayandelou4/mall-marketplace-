import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, MessageCircle, PackageCheck, ShieldCheck, ShoppingBag, Store } from "lucide-react";
import { SiteHeader } from "../components/layout/SiteHeader";
import { SiteFooter } from "../components/layout/SiteFooter";
import { useTheme } from "../features/theme/ThemeContext";
import { cx } from "../styles/theme";

const SECTIONS = [
  { id: "acheter", label: "Acheter" },
  { id: "vendre", label: "Vendre" },
  { id: "commandes", label: "Commandes et messages" },
  { id: "compte", label: "Compte et sécurité" },
  { id: "questions", label: "Questions fréquentes" },
];

function HelpSection({ id, title, icon, t, children }) {
  return (
    <section id={id} className={cx("scroll-mt-24 border-b py-8 last:border-0", t.border)}>
      <div className="mb-5 flex items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
          {icon}
        </span>
        <h2 className={cx("text-lg font-semibold", t.textPrimary)}>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function GuideSteps({ steps, t }) {
  return (
    <ol className="grid gap-5 sm:grid-cols-2">
      {steps.map((step, index) => (
        <li key={step.title} className="flex gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-indigo-200 text-xs font-semibold text-indigo-700 dark:border-indigo-900 dark:text-indigo-300">
            {index + 1}
          </span>
          <div>
            <h3 className={cx("text-sm font-semibold", t.textPrimary)}>{step.title}</h3>
            <p className={cx("mt-1 text-sm leading-6", t.textMuted)}>{step.text}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export default function HelpPage() {
  const { t } = useTheme();

  return (
    <div className={cx("flex min-h-screen flex-col", t.pageBg, t.textPrimary)}>
      <SiteHeader />

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 lg:py-12">
        <header className={cx("border-b pb-7", t.border)}>
          <p className="text-xs font-semibold uppercase text-indigo-600">Centre d’aide</p>
          <h1 className={cx("mt-2 text-3xl font-semibold", t.textPrimary)}>Les repères pour bien commencer</h1>
          <p className={cx("mt-3 max-w-2xl text-sm leading-6", t.textMuted)}>
            Trouvez un article, échangez avec le vendeur, puis convenez ensemble de la remise. Le paiement se fait en espèces, directement au moment de la remise.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link to="/catalogue" className="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700">
              Parcourir le catalogue <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/vendeur" className={cx("inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-semibold", t.border, t.textPrimary)}>
              <Store className="h-4 w-4" /> Vendre sur Mall
            </Link>
          </div>
        </header>

        <div className="grid gap-8 lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-14">
          <nav aria-label="Rubriques de l’aide" className="lg:sticky lg:top-24 lg:h-fit lg:py-8">
            <p className={cx("mb-3 text-xs font-semibold uppercase", t.textMuted)}>Dans cette page</p>
            <ul className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible">
              {SECTIONS.map((section) => (
                <li key={section.id} className="shrink-0">
                  <a href={`#${section.id}`} className={cx("block rounded-lg px-3 py-2 text-sm hover:bg-indigo-50 hover:text-indigo-700 dark:hover:bg-indigo-950 dark:hover:text-indigo-300", t.textMuted)}>
                    {section.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <div className="min-w-0">
            <HelpSection id="acheter" title="Acheter un produit ou réserver un service" icon={<ShoppingBag className="h-4 w-4" aria-hidden="true" />} t={t}>
              <GuideSteps t={t} steps={[
                { title: "Cherchez", text: "Parcourez les produits et services. Filtrez par catégorie, ville, prix ou disponibilité, puis ouvrez une annonce pour en vérifier les détails." },
                { title: "Contactez le vendeur", text: "Posez vos questions dans la messagerie Mall. Pour un service, contactez le prestataire afin de convenir des disponibilités et des conditions." },
                { title: "Passez commande", text: "Pour un produit disponible, ajoutez-le au panier puis validez la commande. Une adresse est demandée uniquement si l’annonce prévoit une livraison." },
                { title: "Convenez de la remise", text: "Échangez avec le vendeur pour fixer les modalités. Le paiement se fait en espèces, en main propre, au moment de la remise." },
              ]} />
              <p className={cx("mt-5 border-l-2 border-amber-400 pl-3 text-sm leading-6", t.textMuted)}>
                Le paiement en ligne et Mobile Money ne sont pas encore disponibles sur Mall. Une commande enregistrée n’est pas un paiement.
              </p>
            </HelpSection>

            <HelpSection id="vendre" title="Publier une annonce" icon={<Store className="h-4 w-4" aria-hidden="true" />} t={t}>
              <GuideSteps t={t} steps={[
                { title: "Créez votre compte", text: "Connectez-vous et confirmez votre adresse e-mail si cela vous est demandé avant votre première publication." },
                { title: "Complétez l’annonce", text: "Dans le tableau de bord vendeur, ajoutez un titre, une description, une catégorie, un prix, une devise, votre ville et jusqu’à trois photos." },
                { title: "Précisez les conditions", text: "Pour un produit, indiquez son état, le stock et le mode de remise ou de livraison. Pour un service, précisez le tarif et ses modalités." },
                { title: "Suivez vos annonces", text: "Retrouvez leur statut dans le tableau de bord. Vous pouvez modifier une annonce ou l’archiver lorsqu’elle n’est plus disponible." },
              ]} />
              <Link to="/vendeur" className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-indigo-600 hover:underline">
                Ouvrir le tableau de bord vendeur <ArrowRight className="h-4 w-4" />
              </Link>
            </HelpSection>

            <HelpSection id="commandes" title="Suivre une commande et gérer vos messages" icon={<PackageCheck className="h-4 w-4" aria-hidden="true" />} t={t}>
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <h3 className={cx("text-sm font-semibold", t.textPrimary)}>Vos commandes</h3>
                  <p className={cx("mt-1 text-sm leading-6", t.textMuted)}>
                    Retrouvez l’état et le détail de vos commandes dans « Mes commandes ». Après avoir reçu l’article, confirmez sa réception. En cas de problème, signalez un litige depuis la commande.
                  </p>
                  <Link to="/mes-commandes" className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-indigo-600 hover:underline">
                    Voir mes commandes <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
                <div>
                  <h3 className={cx("flex items-center gap-2 text-sm font-semibold", t.textPrimary)}><MessageCircle className="h-4 w-4 text-indigo-600" /> La messagerie</h3>
                  <p className={cx("mt-1 text-sm leading-6", t.textMuted)}>
                    Retrouvez vos échanges dans « Messages ». Les options sous chaque message permettent de répondre, modifier un message récent, le supprimer ou le signaler. Le menu en haut à droite gère la conversation et la sélection de plusieurs messages.
                  </p>
                  <Link to="/messages" className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-indigo-600 hover:underline">
                    Ouvrir les messages <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>
            </HelpSection>

            <HelpSection id="compte" title="Compte et sécurité" icon={<ShieldCheck className="h-4 w-4" aria-hidden="true" />} t={t}>
              <ul className={cx("grid gap-3 text-sm leading-6 sm:grid-cols-2", t.textMuted)}>
                <li><strong className={t.textPrimary}>Favoris :</strong> enregistrez des annonces pour les retrouver facilement.</li>
                <li><strong className={t.textPrimary}>Notifications :</strong> consultez les nouveautés liées à votre compte.</li>
                <li><strong className={t.textPrimary}>Adresse :</strong> vos adresses enregistrées restent privées et ne sont communiquées qu’aux personnes autorisées à traiter la commande.</li>
                <li><strong className={t.textPrimary}>Signalement :</strong> signalez une annonce depuis sa page ou un message depuis ses options.</li>
              </ul>
            </HelpSection>

            <HelpSection id="questions" title="Questions fréquentes" icon={<MessageCircle className="h-4 w-4" aria-hidden="true" />} t={t}>
              <div className="divide-y">
                <details className={cx("border-b py-4", t.border)}>
                  <summary className={cx("cursor-pointer text-sm font-semibold", t.textPrimary)}>Mall encaisse-t-il le paiement ?</summary>
                  <p className={cx("mt-2 text-sm leading-6", t.textMuted)}>Non. Pour le moment, vous payez le vendeur en espèces au moment de la remise. Ne considérez pas la commande comme payée avant cette remise.</p>
                </details>
                <details className={cx("border-b py-4", t.border)}>
                  <summary className={cx("cursor-pointer text-sm font-semibold", t.textPrimary)}>Dois-je fournir une adresse ?</summary>
                  <p className={cx("mt-2 text-sm leading-6", t.textMuted)}>Seulement si le produit doit être livré. Pour une remise en main propre, aucune adresse de livraison n’est nécessaire.</p>
                </details>
                <details className={cx("border-b py-4", t.border)}>
                  <summary className={cx("cursor-pointer text-sm font-semibold", t.textPrimary)}>Puis-je acheter un service dans le panier ?</summary>
                  <p className={cx("mt-2 text-sm leading-6", t.textMuted)}>Non. Contactez le prestataire depuis l’annonce pour vous entendre sur la réservation, le tarif et les disponibilités.</p>
                </details>
                <details className={cx("py-4", t.border)}>
                  <summary className={cx("cursor-pointer text-sm font-semibold", t.textPrimary)}>Comment signaler un problème ?</summary>
                  <p className={cx("mt-2 text-sm leading-6", t.textMuted)}>Pour une commande, utilisez « Signaler un litige » dans « Mes commandes ». Vous pouvez aussi signaler une annonce ou un message depuis son menu d’options.</p>
                </details>
              </div>
            </HelpSection>
          </div>
        </div>
      </main>

      <SiteFooter t={t} />
    </div>
  );
}