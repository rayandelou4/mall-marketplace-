const CLOUDINARY_CLOUD = import.meta.env.VITE_CLOUDINARY_CLOUD_NAME || "f63hzbo5";
const CLOUDINARY_UPLOAD_PRESET = import.meta.env.VITE_CLOUDINARY_UPLOAD_PRESET || "easy_mall_unsigned";
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
const MAX_IMAGE_EDGE = 1600;

async function decodeImage(file) {
  if (typeof createImageBitmap === "function") {
    return createImageBitmap(file);
  }

  const url = URL.createObjectURL(file);
  const image = new Image();
  try {
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = reject;
      image.src = url;
    });
    return {
      source: image,
      width: image.naturalWidth,
      height: image.naturalHeight,
      close: () => URL.revokeObjectURL(url),
    };
  } catch (error) {
    URL.revokeObjectURL(url);
    throw error;
  }
}

async function prepareImage(file) {
  const supportedTypes = new Set([
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/avif",
    "image/heic",
    "image/heif",
  ]);
  if (!supportedTypes.has(file.type)) {
    throw new Error("Choisissez une image JPEG, PNG, WebP, AVIF ou HEIC.");
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error("Chaque photo doit peser moins de 20 Mo.");
  }

  let bitmap;
  try {
    bitmap = await decodeImage(file);
  } catch {
    throw new Error("Cette image ne peut pas être décodée sur cet appareil.");
  }

  const scale = Math.min(1, MAX_IMAGE_EDGE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  const context = canvas.getContext("2d");
  if (!context) {
    bitmap.close();
    throw new Error("La préparation de l’image a échoué.");
  }
  context.drawImage(bitmap.source || bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  const compressed = await new Promise((resolve) => {
    canvas.toBlob(resolve, "image/webp", 0.8);
  });
  if (!compressed) {
    throw new Error("La compression de l’image a échoué.");
  }
  if (compressed.size >= file.size) return file;

  const extension = compressed.type === "image/webp" ? "webp" : "jpg";
  return new File([compressed], `mall-listing.${extension}`, {
    type: compressed.type,
    lastModified: Date.now(),
  });
}

export function optimizedImageUrl(url, width) {
  if (!url) return url;

  try {
    const imageUrl = new URL(url);
    if (imageUrl.hostname !== "res.cloudinary.com") return url;

    const uploadPath = "/image/upload/";
    if (!imageUrl.pathname.includes(uploadPath)) return url;

    imageUrl.pathname = imageUrl.pathname.replace(
      uploadPath,
      `${uploadPath}f_auto,q_auto,w_${width},c_limit/`
    );
    return imageUrl.toString();
  } catch {
    return url;
  }
}

export async function uploadToCloudinary(file) {
  if (!file) {
    throw new Error("Aucun fichier sélectionné.");
  }

  const optimizedFile = await prepareImage(file);
  const formData = new FormData();
  formData.append("file", optimizedFile);
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

