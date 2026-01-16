/**
 * Setting Card Component
 *
 * A card container for grouping related settings.
 */

import { ReactNode } from 'react';

interface SettingCardProps {
  title: string;
  description?: string;
  children: ReactNode;
  action?: ReactNode;
}

export function SettingCard({ title, description, children, action }: SettingCardProps) {
  return (
    <div className="bg-white dark:bg-stone-900 rounded-lg border border-stone-200 dark:border-stone-700 shadow-sm">
      <div className="px-6 py-4 border-b border-stone-200 dark:border-stone-700 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-stone-900 dark:text-stone-100">
            {title}
          </h3>
          {description && (
            <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
              {description}
            </p>
          )}
        </div>
        {action && <div>{action}</div>}
      </div>
      <div className="px-6 py-4 divide-y divide-stone-100 dark:divide-stone-800">
        {children}
      </div>
    </div>
  );
}
