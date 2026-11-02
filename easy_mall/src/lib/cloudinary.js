const CLOUDINARY_CLOUD = import.meta.env.VITE_CLOUDINARY_CLOUD_NAME || "f63hzbo5";
const CLOUDINARY_UPLOAD_PRESET = import.meta.env.VITE_CLOUDINARY_UPLOAD_PRESET || "easy_mall_unsigned";

export async function uploadToCloudinary(file) {
  if (!file) {
    throw new Error("Aucun fichier sélectionné.");
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("upload_preset", CLOUDINARY_UPLOAD_PRESET);
  formData.append("cloud_name", CLOUDINARY_CLOUD);

  const response = await fetch(`https://api.cloudinary.com/v1_1/${CLOUDINARY_CLOUD}/image/upload`, {
    method: "POST",
    body: formData,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.secure_url) {
    const message = data.error?.message || "Le téléchargement Cloudinary a échoué.";
    throw new Error(message);
  }

  return data.secure_url;
}

