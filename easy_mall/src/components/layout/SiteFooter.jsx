import React from "react";
import { FaInstagram, FaFacebook, FaTwitter } from "react-icons/fa";
import { cx } from "../../styles/theme";
import { API_BASE_URL } from "../../lib/apiClient";

const COLUMNS = [
  { title: "Découvrir", links: ["Catégories", "Produits récents", "Vendeurs"] },
  { title: "Vendre", links: ["Publier une annonce", "Tableau de bord vendeur"] },
  { title: "Assistance", links: ["Centre d'aide", "Comment ça marche", "Nous contacter", "Signaler un problème"] },
  { title: "Légal", links: ["Conditions d'utilisation", "Confidentialité", "Politique de litiges"] },
];

export function SiteFooter({ t }) {
  return (
    <footer className={cx("border-t py-12", t.border)}>
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <span className="text-2xl font-semibold text-indigo-600">Mall</span>
            <p className={cx("mt-3 max-w-xs text-sm", t.textMuted)}>La marketplace d'occasion et de neuf pensée pour l'Afrique.</p>
            <div className="mt-4 flex gap-3">
              <FaInstagram className={cx("h-4 w-4", t.textMuted)} />
              <FaFacebook className={cx("h-4 w-4", t.textMuted)} />
              <FaTwitter className={cx("h-4 w-4", t.textMuted)} />
            </div>
          </div>
          {COLUMNS.map((col) => (
            <div key={col.title}>
              <p className={cx("text-sm font-semibold", t.textPrimary)}>{col.title}</p>
              <ul className="mt-3 flex flex-col gap-2">
                {col.links.map((link) => <li key={link}><a href="#" className={cx("text-sm", t.textMuted)}>{link}</a></li>)}
              </ul>
            </div>
          ))}
        </div>
        <div className={cx("mt-10 flex flex-col gap-3 border-t pt-6 text-xs sm:flex-row sm:items-center sm:justify-between", t.border, t.textMuted)}>
          <span>© 2026 Mall. Tous droits réservés.</span>
          <span>API : {API_BASE_URL}</span>
        </div>
      </div>
    </footer>
  );
}
