import type { ButtonHTMLAttributes } from 'react'

/** A link that is a button, as every dashboard writes the ones that go to another page — a location, a visit, an SD card: the text, underlined with dots, that turns blue under the pointer. */
export default function LinkButton({ className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" {...props}
            className={`rounded underline decoration-dotted underline-offset-4 hover:text-blue-600 dark:hover:text-blue-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${className}`} />
  )
}
