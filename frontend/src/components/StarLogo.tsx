import { memo } from 'react'

/**
 * 小星助手 · 品牌 Logo 组件
 *
 * 一个会眨眼、抖耳朵、悬浮的猫耳小机器人，替代旧版 <StarFilled />。
 * 全部用纯 CSS keyframes 驱动，不依赖 JS 与外部图片。
 *
 * 变体（覆盖三处实际使用场景）：
 *   on-gold   — 放在金色浮岛深色盒子里（侧边栏）：深身 + 亮眼
 *   on-light  — 放在金色渐变方块里（欢迎页）：金身 + 深眼 + 胸口白星
 *   plain     — 直接放浅色背景（备用）：金身 + 深眼 + 胸口白星
 *
 * 尺寸：任意，组件会按 100% 填满父容器。父容器决定 size。
 */

export type StarLogoVariant = 'on-gold' | 'on-light' | 'plain'

interface Props {
  variant?: StarLogoVariant
  className?: string
}

function StarLogoImpl({ variant = 'on-light', className = '' }: Props) {
  return (
    <div
      className={`star-logo star-logo--${variant} ${className}`}
      role="img"
      aria-label="小星助手"
    >
      <svg viewBox="0 0 64 64" className="star-logo__svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          {/* 金身渐变（on-light / plain） */}
          <linearGradient id="sl-body-gold" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#f5d573" />
            <stop offset="55%" stopColor="#c9952b" />
            <stop offset="100%" stopColor="#8c620e" />
          </linearGradient>
          {/* 深身渐变（on-gold 浮岛里的版本，盒子本身已经是深色） */}
          <linearGradient id="sl-body-dark" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#1e3a5f" />
            <stop offset="100%" stopColor="#0f1a2e" />
          </linearGradient>
          {/* 脸屏 */}
          <linearGradient id="sl-face" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0a1426" />
            <stop offset="100%" stopColor="#0f1a2e" />
          </linearGradient>
        </defs>

        {/* ── 头（浮动 + 轻微摆动） ── */}
        <g className="star-logo__head">
          {/* 猫耳 */}
          <g className="star-logo__ear star-logo__ear--l">
            <path d="M 18 16 L 14 4 L 26 12 Z" fill="url(#sl-body-gold)" className="star-logo__ear-outer" />
            <path d="M 18.5 13.5 L 17 8 L 22 11.5 Z" fill="#fde68a" className="star-logo__ear-inner" />
          </g>
          <g className="star-logo__ear star-logo__ear--r">
            <path d="M 46 16 L 50 4 L 38 12 Z" fill="url(#sl-body-gold)" className="star-logo__ear-outer" />
            <path d="M 45.5 13.5 L 47 8 L 42 11.5 Z" fill="#fde68a" className="star-logo__ear-inner" />
          </g>

          {/* 头身 — 根据 variant 切换填色 */}
          <ellipse
            cx="32"
            cy="36"
            rx="22"
            ry="20"
            fill={variant === 'on-gold' ? 'url(#sl-body-dark)' : 'url(#sl-body-gold)'}
            className="star-logo__body"
          />

          {/* 脸屏 */}
          <rect
            x="14"
            y="28"
            width="36"
            height="18"
            rx="9"
            fill="url(#sl-face)"
            className="star-logo__face"
          />

          {/* 眼睛（左） */}
          <g className="star-logo__eye star-logo__eye--l">
            <ellipse cx="22" cy="37" rx="3" ry="3.6" fill="#5eead4" className="star-logo__eye-pupil" />
            <circle cx="23" cy="35.5" r="1" fill="#ffffff" className="star-logo__eye-shine" />
          </g>
          {/* 眼睛（右） */}
          <g className="star-logo__eye star-logo__eye--r">
            <ellipse cx="42" cy="37" rx="3" ry="3.6" fill="#5eead4" className="star-logo__eye-pupil" />
            <circle cx="43" cy="35.5" r="1" fill="#ffffff" className="star-logo__eye-shine" />
          </g>

          {/* 胸口小星 — 只在浅/金身版本显示 */}
          {variant !== 'on-gold' && (
            <path
              d="M 32 50 L 33 53 L 36 53 L 33.5 55 L 34.5 58 L 32 56 L 29.5 58 L 30.5 55 L 28 53 L 31 53 Z"
              fill="#ffffff"
              className="star-logo__chest-star"
            />
          )}
        </g>
      </svg>
    </div>
  )
}

export const StarLogo = memo(StarLogoImpl)
export default StarLogo