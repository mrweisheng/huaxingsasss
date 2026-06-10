import { memo } from 'react'

/**
 * 小星助手 · 品牌 Logo（Welcome 专享版）
 *
 * 设计目标：复刻 mockup-welcome.png 的奶油金色猫耳机器人形象
 * 渲染策略：纯 SVG（无外部图片）+ 多层 radialGradient + feGaussianBlur
 *           模拟 PNG 的柔光质感，再叠加 CSS keyframes 做动效。
 *
 * 仅用于大尺寸场景（≥80px），如欢迎页主 logo。
 * 缩到 32px 以下细节会丢，不推荐小尺寸使用 —— 那就用回 <StarFilled />。
 */

interface Props {
  size?: number | string
  className?: string
}

function StarLogoWelcomeImpl({ size = 180, className = '' }: Props) {
  return (
    <div
      className={`star-logo-welcome ${className}`}
      style={{ width: size, height: size }}
      role="img"
      aria-label="小星助手"
    >
      <svg
        viewBox="0 0 200 200"
        xmlns="http://www.w3.org/2000/svg"
        style={{ width: '100%', height: '100%', overflow: 'visible' }}
      >
        <defs>
          {/* ── 外圈光晕（核心氛围）── */}
          <radialGradient id="sw-halo-outer" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#f5d573" stopOpacity="0.55" />
            <stop offset="40%" stopColor="#e8b84b" stopOpacity="0.35" />
            <stop offset="75%" stopColor="#c9952b" stopOpacity="0.1" />
            <stop offset="100%" stopColor="#c9952b" stopOpacity="0" />
          </radialGradient>

          <radialGradient id="sw-halo-inner" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fff5d8" stopOpacity="0.85" />
            <stop offset="60%" stopColor="#f5e6c8" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#f5e6c8" stopOpacity="0" />
          </radialGradient>

          {/* ── 身体奶油金渐变（高光偏左上）── */}
          <radialGradient id="sw-body" cx="38%" cy="32%" r="70%">
            <stop offset="0%" stopColor="#fff5d8" />
            <stop offset="35%" stopColor="#f0d488" />
            <stop offset="70%" stopColor="#d4a23a" />
            <stop offset="100%" stopColor="#8c620e" />
          </radialGradient>

          {/* ── 身体底面阴影（底部更暗）── */}
          <linearGradient id="sw-body-shadow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="60%" stopColor="#000" stopOpacity="0" />
            <stop offset="100%" stopColor="#000" stopOpacity="0.18" />
          </linearGradient>

          {/* ── 面屏（深石板蓝）── */}
          <radialGradient id="sw-face" cx="50%" cy="40%" r="70%">
            <stop offset="0%" stopColor="#2a3a55" />
            <stop offset="55%" stopColor="#0f1a2e" />
            <stop offset="100%" stopColor="#050a16" />
          </radialGradient>

          {/* ── 眼睛青绿 ── */}
          <radialGradient id="sw-eye" cx="40%" cy="35%" r="65%">
            <stop offset="0%" stopColor="#a7f3d0" />
            <stop offset="60%" stopColor="#5eead4" />
            <stop offset="100%" stopColor="#14b8a6" />
          </radialGradient>

          {/* ── 扬声器侧耳（深金圆）── */}
          <radialGradient id="sw-ear" cx="35%" cy="35%" r="70%">
            <stop offset="0%" stopColor="#f5d573" />
            <stop offset="60%" stopColor="#d4a23a" />
            <stop offset="100%" stopColor="#7a4f0c" />
          </radialGradient>

          {/* ── 柔光滤镜（让渐变有"融化感"）── */}
          <filter id="sw-soft" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="0.4" />
          </filter>

          <filter id="sw-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          <filter id="sw-halo-blur" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="6" />
          </filter>
        </defs>

        {/* ══════ ① 外圈光晕（双层叠加）══════ */}
        <g className="sw-halo">
          <circle cx="100" cy="100" r="92" fill="url(#sw-halo-outer)" filter="url(#sw-halo-blur)" />
          <circle cx="100" cy="100" r="68" fill="url(#sw-halo-inner)" filter="url(#sw-halo-blur)" />
        </g>

        {/* ══════ ② 猫耳（先画耳，在身体后面）══════ */}
        <g className="sw-ears">
          {/* 左耳 */}
          <g className="sw-ear sw-ear--l">
            <path
              d="M 70 78 Q 64 50 78 38 Q 88 50 92 76 Z"
              fill="url(#sw-ear)"
              stroke="#7a4f0c"
              strokeWidth="0.6"
              strokeOpacity="0.5"
            />
            {/* 耳内粉色绒 */}
            <path
              d="M 75 70 Q 73 55 80 50 Q 84 60 86 72 Z"
              fill="#f9c5b0"
              opacity="0.85"
            />
          </g>
          {/* 右耳 */}
          <g className="sw-ear sw-ear--r">
            <path
              d="M 130 78 Q 136 50 122 38 Q 112 50 108 76 Z"
              fill="url(#sw-ear)"
              stroke="#7a4f0c"
              strokeWidth="0.6"
              strokeOpacity="0.5"
            />
            <path
              d="M 125 70 Q 127 55 120 50 Q 116 60 114 72 Z"
              fill="#f9c5b0"
              opacity="0.85"
            />
          </g>
        </g>

        {/* ══════ ③ 身体（圆角蛋形）══════ */}
        <g className="sw-body">
          {/* 头身主体 */}
          <ellipse
            cx="100"
            cy="98"
            rx="56"
            ry="52"
            fill="url(#sw-body)"
            filter="url(#sw-soft)"
          />
          {/* 底部阴影层（增强立体） */}
          <ellipse
            cx="100"
            cy="98"
            rx="56"
            ry="52"
            fill="url(#sw-body-shadow)"
          />
          {/* 头部高光（左上柔光斑） */}
          <ellipse
            cx="78"
            cy="72"
            rx="20"
            ry="14"
            fill="#fff5d8"
            opacity="0.55"
            filter="url(#sw-soft)"
          />

          {/* 脖子阴影环（身体与头之间的凹陷感） */}
          <ellipse
            cx="100"
            cy="148"
            rx="42"
            ry="6"
            fill="#7a4f0c"
            opacity="0.35"
          />
        </g>

        {/* ══════ ④ 扬声器侧耳（圆形小蛋）══════ */}
        <g className="sw-side-speakers">
          <ellipse cx="46" cy="104" rx="11" ry="13" fill="url(#sw-ear)" stroke="#7a4f0c" strokeOpacity="0.4" strokeWidth="0.5" />
          <ellipse cx="46" cy="100" rx="5" ry="6" fill="#fff5d8" opacity="0.5" />
          <ellipse cx="154" cy="104" rx="11" ry="13" fill="url(#sw-ear)" stroke="#7a4f0c" strokeOpacity="0.4" strokeWidth="0.5" />
          <ellipse cx="154" cy="100" rx="5" ry="6" fill="#fff5d8" opacity="0.5" />
        </g>

        {/* ══════ ⑤ 面屏（深色椭圆，带斜向高光）══════ */}
        <g className="sw-face-screen">
          <ellipse cx="100" cy="98" rx="38" ry="28" fill="url(#sw-face)" />
          {/* 面屏边缘柔光描边 */}
          <ellipse cx="100" cy="98" rx="38" ry="28" fill="none" stroke="#5eead4" strokeWidth="0.8" strokeOpacity="0.18" />
          {/* 斜向高光（屏幕反光） */}
          <ellipse cx="84" cy="86" rx="12" ry="4" fill="#fff" opacity="0.12" transform="rotate(-25 84 86)" />
        </g>

        {/* ══════ ⑥ 眼睛（青绿 + 眯眼笑）══════ */}
        <g className="sw-eyes">
          {/* 左眼 */}
          <g className="sw-eye sw-eye--l">
            <ellipse cx="84" cy="100" rx="7" ry="9" fill="url(#sw-eye)" filter="url(#sw-glow)" className="sw-eye-pupil" />
            {/* 眼内高光 */}
            <ellipse cx="81" cy="96" rx="2.5" ry="3" fill="#fff" opacity="0.95" />
          </g>
          {/* 右眼 */}
          <g className="sw-eye sw-eye--r">
            <ellipse cx="116" cy="100" rx="7" ry="9" fill="url(#sw-eye)" filter="url(#sw-glow)" className="sw-eye-pupil" />
            <ellipse cx="113" cy="96" rx="2.5" ry="3" fill="#fff" opacity="0.95" />
          </g>
          {/* 嘴巴（眯眼笑） */}
          <path
            d="M 94 113 Q 100 117 106 113"
            stroke="#5eead4"
            strokeWidth="2"
            strokeLinecap="round"
            fill="none"
            className="sw-mouth"
            filter="url(#sw-glow)"
          />
        </g>

        {/* ══════ ⑦ 胸口小星（金色五角星 + 深描边）══════ */}
        <g className="sw-chest">
          <path
            d="M 100 152 L 103 159 L 111 159 L 105 164 L 107 171 L 100 167 L 93 171 L 95 164 L 89 159 L 97 159 Z"
            fill="#f5d573"
            stroke="#a87a18"
            strokeWidth="0.8"
            strokeLinejoin="round"
            className="sw-chest-star"
          />
          {/* 星的高光 */}
          <path
            d="M 100 153 L 102 158 L 104 158 L 102 159.5 L 103 161.5 L 100 160 L 97 161.5 L 98 159.5 L 96 158 L 98 158 Z"
            fill="#fff5d8"
            opacity="0.6"
          />
        </g>
      </svg>
    </div>
  )
}

export const StarLogoWelcome = memo(StarLogoWelcomeImpl)
export default StarLogoWelcome