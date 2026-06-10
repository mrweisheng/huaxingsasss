/**
 * 图片压缩：图片走 Canvas 等比缩放 + JPEG 重编码；非图片原样返回。
 *
 * - 仅当 file.type 以 "image/" 开头才压缩；GIF 跳过（保留动画）。
 * - 最长边超过 maxEdge 才缩放，否则保持原尺寸。
 * - 若压缩后反而更大（比如本来已是高压缩 JPEG），返回原文件。
 */
export async function compressImage(
  file: File,
  options: { maxEdge?: number; quality?: number } = {},
): Promise<File> {
  const { maxEdge = 1920, quality = 0.8 } = options

  if (!file.type.startsWith('image/') || file.type === 'image/gif') {
    return file
  }

  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file)
  } catch {
    return file
  }

  const { width, height } = bitmap
  const longest = Math.max(width, height)
  const scale = longest > maxEdge ? maxEdge / longest : 1
  const targetW = Math.round(width * scale)
  const targetH = Math.round(height * scale)

  const canvas = document.createElement('canvas')
  canvas.width = targetW
  canvas.height = targetH
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    bitmap.close()
    return file
  }
  ctx.drawImage(bitmap, 0, 0, targetW, targetH)
  bitmap.close()

  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, 'image/jpeg', quality)
  })
  if (!blob || blob.size >= file.size) {
    return file
  }

  const baseName = file.name.replace(/\.[^.]+$/, '')
  return new File([blob], `${baseName}.jpg`, {
    type: 'image/jpeg',
    lastModified: file.lastModified,
  })
}
