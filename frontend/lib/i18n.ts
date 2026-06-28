import kaMessages from "../messages/ka.json";
import ruMessages from "../messages/ru.json";

export const SUPPORTED_LOCALES = ["ru", "ka"] as const;
export const DEFAULT_LOCALE = "ru";

export type Locale = (typeof SUPPORTED_LOCALES)[number];

type MessageNode = string | { [key: string]: MessageNode };

const dictionaries: Record<Locale, MessageNode> = {
  ru: ruMessages,
  ka: kaMessages,
};

export function isSupportedLocale(value: string | undefined | null): value is Locale {
  return SUPPORTED_LOCALES.includes(value as Locale);
}

export function normalizeLocale(value: string | undefined | null): Locale {
  return isSupportedLocale(value) ? value : DEFAULT_LOCALE;
}

export function t(locale: Locale, key: string): string {
  const dictionary = dictionaries[locale] ?? dictionaries[DEFAULT_LOCALE];
  const fallback = dictionaries[DEFAULT_LOCALE];
  return lookup(dictionary, key) ?? lookup(fallback, key) ?? key;
}

function lookup(dictionary: MessageNode, key: string): string | undefined {
  const value = key.split(".").reduce<MessageNode | undefined>((current, part) => {
    if (typeof current !== "object" || current === null) {
      return undefined;
    }
    return current[part];
  }, dictionary);
  return typeof value === "string" ? value : undefined;
}
