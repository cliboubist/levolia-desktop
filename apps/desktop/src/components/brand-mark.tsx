import { cn } from '@/lib/utils'

// Levolia brand badge. Placeholder mark until the final logo asset is dropped
// into public/ — swap the inner SVG for an <img> when it is available.
export function BrandMark({ className, ...props }: React.ComponentProps<'span'>) {
  return (
    <span
      className={cn(
        'inline-flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-md bg-[#0f172a] text-white',
        className
      )}
      {...props}
    >
      <svg aria-hidden="true" className="size-[62%]" fill="none" viewBox="0 0 24 24">
        <path d="M6 4v14h12" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
      </svg>
    </span>
  )
}
