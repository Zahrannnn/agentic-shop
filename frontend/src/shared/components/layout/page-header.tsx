type PageHeaderProps = {
  title: string;
  description?: string;
};

export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <header className="space-y-1">
      <h1 className="text-2xl font-semibold tracking-normal">{title}</h1>
      {description ? (
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          {description}
        </p>
      ) : null}
    </header>
  );
}
