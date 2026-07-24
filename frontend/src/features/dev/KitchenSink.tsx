import { useState } from 'react';
import { Moon, Sun, Plus, Search, Filter, Trash2, User, Info } from 'lucide-react';
import { useThemeStore } from '@/stores/themeStore';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
  Avatar,
  Badge,
  Button,
  Card,
  CardBody,
  CardFooter,
  CardHeader,
  CardTitle,
  Checkbox,
  Combobox,
  CommandPalette,
  ConfirmDialog,
  DatePicker,
  DateRangePicker,
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DotPulse,
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  EmptyState,
  ErrorState,
  FormField,
  IconButton,
  Input,
  KeyValueList,
  MultiSelect,
  NumberInput,
  Pagination,
  PhoneInput,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Progress,
  RadioGroup,
  RadioOption,
  RankBadge,
  Select,
  Separator,
  Skeleton,
  Slider,
  Spinner,
  Stat,
  StatusBadge,
  Switch,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
  toast,
  Toaster,
  Tooltip,
  TooltipProvider,
} from '@/components/ui';
import { SPECIALIZATIONS, STATIONS } from '@/lib/constants';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-h2 text-ink">{title}</h2>
      <div className="rounded-md border border-hairline bg-surface p-6 shadow-e1">{children}</div>
    </section>
  );
}

const TYPE_TOKENS = [
  ['display-lg', 'text-display-lg font-display'],
  ['display', 'text-display font-display'],
  ['h1', 'text-h1 font-display'],
  ['h2', 'text-h2 font-display'],
  ['h3', 'text-h3 font-display'],
  ['body-lg', 'text-body-lg'],
  ['body', 'text-body'],
  ['body-sm', 'text-body-sm'],
  ['caption', 'text-caption'],
  ['label', 'text-label font-mono uppercase'],
  ['data', 'text-data font-mono'],
  ['data-lg', 'text-data-lg font-mono'],
  ['data-xl', 'text-data-xl font-mono'],
] as const;

// Static class names — Tailwind JIT cannot see dynamically built strings.
const PRIMARY_SWATCHES: [string, string][] = [
  ['primary-900', 'bg-primary-900'],
  ['primary-800', 'bg-primary-800'],
  ['primary-700', 'bg-primary-700'],
  ['primary-600', 'bg-primary-600'],
  ['primary-500', 'bg-primary-500'],
  ['primary-400', 'bg-primary-400'],
  ['primary-300', 'bg-primary-300'],
  ['primary-200', 'bg-primary-200'],
  ['primary-100', 'bg-primary-100'],
  ['primary-50', 'bg-primary-50'],
];
const SURFACE_SWATCHES: [string, string][] = [
  ['canvas', 'bg-canvas'],
  ['surface', 'bg-surface'],
  ['surface-raised', 'bg-surface-raised'],
  ['surface-sunken', 'bg-surface-sunken'],
];
const TEXT_SWATCHES: [string, string][] = [
  ['ink', 'text-ink'],
  ['text-secondary', 'text-text-secondary'],
  ['text-muted', 'text-text-muted'],
  ['text-disabled', 'text-text-disabled'],
];

export function KitchenSink() {
  const { theme, toggle } = useThemeStore();
  const [num, setNum] = useState<number | ''>(11);
  const [phone, setPhone] = useState('+256 772 419 273');
  const [spec, setSpec] = useState('');
  const [stations, setStations] = useState<string[]>([]);
  const [radio, setRadio] = useState('standard');
  const [checked, setChecked] = useState(true);
  const [enabled, setEnabled] = useState(true);
  const [weight, setWeight] = useState<number[]>([30]);
  const [date, setDate] = useState<string | undefined>('2026-08-14');
  const [range, setRange] = useState<{ from?: string; to?: string }>({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [page, setPage] = useState(3);

  const specOptions = SPECIALIZATIONS.map((s) => ({ value: s, label: s }));
  const stationOptions = STATIONS.map((s) => ({ value: s.name, label: s.name }));

  return (
    <TooltipProvider delayDuration={200}>
      <div className="min-h-screen bg-canvas">
        <div className="mx-auto max-w-content px-4 py-8 md:px-8">
          {/* Header */}
          <div className="mb-8 flex items-center justify-between gap-4">
            <div className="flex flex-col gap-1">
              <span className="font-mono text-label uppercase text-text-muted">
                Dev · Alignment proving ground
              </span>
              <h1 className="text-display text-ink">Kitchen sink</h1>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={() => setPaletteOpen(true)} icon={<Search size={16} className="shrink-0" />}>
                Command palette
              </Button>
              <IconButton
                label={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
                variant="secondary"
                onClick={toggle}
              >
                {theme === 'dark' ? <Sun size={20} className="shrink-0" /> : <Moon size={20} className="shrink-0" />}
              </IconButton>
            </div>
          </div>

          <div className="flex flex-col gap-10">
            <Section title="Typography">
              <div className="flex flex-col gap-3">
                {TYPE_TOKENS.map(([name, cls]) => (
                  <div key={name} className="grid grid-cols-[120px_1fr] items-baseline gap-4">
                    <span className="font-mono text-label uppercase text-text-muted">{name}</span>
                    <span className={cls}>The quick brown fox — 1,204 · 87.4</span>
                  </div>
                ))}
              </div>
            </Section>

            <Section title="Colour tokens">
              <div className="flex flex-col gap-6">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                  {PRIMARY_SWATCHES.map(([name, cls]) => (
                    <div key={name} className="flex flex-col gap-1">
                      <div className={`h-12 rounded-sm border border-hairline ${cls}`} />
                      <span className="font-mono text-label uppercase text-text-muted">{name}</span>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {SURFACE_SWATCHES.map(([name, cls]) => (
                    <div key={name} className="flex flex-col gap-1">
                      <div className={`h-12 rounded-sm border border-strong ${cls}`} />
                      <span className="font-mono text-label uppercase text-text-muted">{name}</span>
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap gap-4">
                  {TEXT_SWATCHES.map(([name, cls]) => (
                    <span key={name} className={`text-body ${cls}`}>
                      {name}
                    </span>
                  ))}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge tone="success">Available</Badge>
                  <Badge tone="warning">Awaiting</Badge>
                  <Badge tone="danger">Unavailable</Badge>
                  <Badge tone="info">Predicted</Badge>
                  <Badge tone="neutral">Draft</Badge>
                </div>
              </div>
            </Section>

            <Section title="Buttons">
              <div className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center gap-3">
                  <Button variant="primary">Approve this trainer</Button>
                  <Button variant="secondary">Secondary</Button>
                  <Button variant="ghost">Ghost</Button>
                  <Button variant="danger" icon={<Trash2 size={16} className="shrink-0" />}>
                    Deactivate
                  </Button>
                  <Button variant="link">Learn more</Button>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <Button size="sm">Small</Button>
                  <Button size="md">Medium</Button>
                  <Button size="lg">Large</Button>
                  <Button loading>Saving</Button>
                  <Tooltip content="Available once the training has been marked as conducted." onDisabled>
                    <Button disabled>Record evaluation</Button>
                  </Tooltip>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <IconButton label="Add"><Plus size={20} className="shrink-0" /></IconButton>
                  <IconButton label="Filter" variant="secondary"><Filter size={20} className="shrink-0" /></IconButton>
                  <IconButton label="User" variant="primary"><User size={20} className="shrink-0" /></IconButton>
                </div>
              </div>
            </Section>

            <Section title="Loaders">
              <div className="flex flex-wrap items-center gap-8">
                <div className="flex items-center gap-4">
                  <DotPulse size={16} />
                  <DotPulse size={20} />
                  <DotPulse size={24} />
                </div>
                <Separator orientation="vertical" className="h-8" />
                <div className="flex items-center gap-4">
                  <Spinner size={24} />
                  <Spinner size={40} />
                </div>
              </div>
            </Section>

            <Section title="Status badges, ranks & avatars">
              <div className="flex flex-col gap-4">
                <div className="flex flex-wrap gap-2">
                  <StatusBadge kind="programme" value="PREDICTED" />
                  <StatusBadge kind="allocation" value="CONFIRMED" />
                  <StatusBadge kind="availability" value="AVAILABLE" />
                  <StatusBadge kind="availability" value="UNAVAILABLE" />
                  <StatusBadge kind="account" value="DEACTIVATED" />
                  <StatusBadge kind="confidence" value="LOW" />
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <RankBadge rank={1} />
                  <RankBadge rank={2} />
                  <RankBadge rank={12} />
                  <Avatar name="Grace Nabirye" size={24} />
                  <Avatar name="Joseph Okello" size={32} />
                  <Avatar name="Sarah Mugisha" size={40} />
                </div>
              </div>
            </Section>

            <Section title="Form controls">
              <div className="grid gap-5 md:grid-cols-2">
                <FormField label="Force number" help="Five digits as printed on the service record.">
                  <Input placeholder="41927" defaultValue="41927" className="font-mono" />
                </FormField>
                <FormField label="Full name" error="This field is required.">
                  <Input placeholder="Enter full name" invalid />
                </FormField>
                <FormField label="Contact number">
                  <PhoneInput value={phone} onChange={setPhone} />
                </FormField>
                <FormField label="Years of experience">
                  <NumberInput value={num} onChange={setNum} min={0} max={40} suffix="years" />
                </FormField>
                <FormField label="Required specialisation" required>
                  <Combobox value={spec} onChange={setSpec} options={specOptions} />
                </FormField>
                <FormField label="Minimum qualification">
                  <Select
                    options={[
                      { value: 'DIPLOMA', label: 'Diploma' },
                      { value: 'BACHELORS', label: "Bachelor's degree" },
                      { value: 'MASTERS', label: "Master's degree" },
                    ]}
                    placeholder="Any qualification"
                  />
                </FormField>
                <FormField label="Stations" className="md:col-span-2">
                  <MultiSelect values={stations} onChange={setStations} options={stationOptions} />
                </FormField>
                <FormField label="Remarks" className="md:col-span-2">
                  <Textarea placeholder="Add remarks…" maxLength={280} showCount />
                </FormField>
                <FormField label="Start date">
                  <DatePicker value={date} onChange={setDate} />
                </FormField>
                <FormField label="Reporting period">
                  <DateRangePicker value={range} onChange={setRange} />
                </FormField>
              </div>
              <Separator className="my-6" />
              <div className="flex flex-wrap items-center gap-8">
                <label className="flex items-center gap-3">
                  <Checkbox checked={checked} onCheckedChange={(v) => setChecked(Boolean(v))} />
                  <span className="text-body text-ink">Mark as available</span>
                </label>
                <label className="flex items-center gap-3">
                  <Switch checked={enabled} onCheckedChange={setEnabled} />
                  <span className="text-body text-ink">Plain language</span>
                </label>
                <div className="w-full sm:w-56">
                  <RadioGroup value={radio} onValueChange={setRadio}>
                    <RadioOption id="r1" value="standard" label="Standard policy" description="Balanced weighting" />
                    <RadioOption id="r2" value="performance" label="Prioritise proven performance" />
                  </RadioGroup>
                </div>
                <div className="flex-1">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-mono text-label uppercase text-text-muted">Specialisation weight</span>
                    <span className="font-mono text-data text-ink">{weight[0]}</span>
                  </div>
                  <Slider value={weight} onValueChange={setWeight} min={0} max={100} step={1} />
                </div>
              </div>
            </Section>

            <Section title="Cards & stats">
              <div className="grid items-stretch gap-6 md:grid-cols-3">
                <Stat label="Awaiting my approval" value="7" delta={{ value: '2', direction: 'up' }} />
                <Stat label="Predictions ready" value="3" hint="Across all categories" />
                <Stat label="Mean evaluation" value="4.6" delta={{ value: '0.2', direction: 'down' }} />
              </div>
              <div className="mt-6 grid items-stretch gap-6 md:grid-cols-2">
                <Card interactive>
                  <CardHeader>
                    <CardTitle>Interactive card</CardTitle>
                  </CardHeader>
                  <CardBody>
                    <KeyValueList
                      items={[
                        { label: 'Registry', value: 'TPS/ALL/2026/0417', mono: true },
                        { label: 'Programme', value: 'Basic Cybercrime Investigation Course — Intake 14' },
                        { label: 'Approved by', value: 'SSP Grace Nabirye' },
                      ]}
                    />
                  </CardBody>
                  <CardFooter>
                    <Button size="sm">Open</Button>
                    <Button size="sm" variant="ghost">Dismiss</Button>
                  </CardFooter>
                </Card>
                <Card glass>
                  <CardBody>
                    <span className="font-mono text-label uppercase text-text-muted">Glass surface</span>
                    <p className="mt-2 text-body text-ink">
                      Reserved for floating surfaces and the rank-1 prediction card (§4.5).
                    </p>
                  </CardBody>
                </Card>
              </div>
            </Section>

            <Section title="Tabs & accordion">
              <Tabs defaultValue="overview">
                <TabsList>
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="quals">Qualifications</TabsTrigger>
                  <TabsTrigger value="perf">Performance</TabsTrigger>
                </TabsList>
                <TabsContent value="overview">
                  <p className="text-body text-text-secondary">Overview content.</p>
                </TabsContent>
                <TabsContent value="quals">
                  <p className="text-body text-text-secondary">Qualifications content.</p>
                </TabsContent>
                <TabsContent value="perf">
                  <p className="text-body text-text-secondary">Performance content.</p>
                </TabsContent>
              </Tabs>
              <Separator className="my-6" />
              <Accordion type="single" collapsible>
                <AccordionItem value="a">
                  <AccordionTrigger>22 unavailable for these dates (BR-03)</AccordionTrigger>
                  <AccordionContent>Named trainers with the specific reason each was excluded.</AccordionContent>
                </AccordionItem>
                <AccordionItem value="b">
                  <AccordionTrigger>14 do not hold the required specialisation (BR-04)</AccordionTrigger>
                  <AccordionContent>Named trainers and their held specialisations.</AccordionContent>
                </AccordionItem>
              </Accordion>
            </Section>

            <Section title="Overlays">
              <div className="flex flex-wrap items-center gap-3">
                <Dialog>
                  <DialogTrigger asChild>
                    <Button variant="secondary">Open dialog</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Approve allocation</DialogTitle>
                      <DialogDescription>
                        Approve IP Sarah Mugisha for Basic Cybercrime Investigation Course — Intake 14?
                      </DialogDescription>
                    </DialogHeader>
                    <DialogBody>
                      <KeyValueList
                        items={[
                          { label: 'Score', value: '87.4 out of 100', mono: true },
                          { label: 'Rank', value: '1st', mono: true },
                        ]}
                      />
                    </DialogBody>
                    <DialogFooter>
                      <Button variant="secondary">Cancel</Button>
                      <Button>Approve</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>

                <Button variant="secondary" onClick={() => setConfirmOpen(true)}>
                  Confirm dialog
                </Button>
                <ConfirmDialog
                  open={confirmOpen}
                  onOpenChange={setConfirmOpen}
                  title="Deactivate account?"
                  description="This account will be unable to sign in. This can be reversed later."
                  confirmLabel="Deactivate"
                  tone="danger"
                  onConfirm={() => {
                    toast.success('Account deactivated');
                  }}
                />

                <Drawer>
                  <DrawerTrigger asChild>
                    <Button variant="secondary">Open drawer</Button>
                  </DrawerTrigger>
                  <DrawerContent>
                    <DrawerHeader>
                      <DrawerTitle>Weight studio</DrawerTitle>
                    </DrawerHeader>
                    <DrawerBody>
                      <p className="text-body text-text-secondary">Slider controls live here (§12.6).</p>
                    </DrawerBody>
                  </DrawerContent>
                </Drawer>

                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="secondary">Popover</Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-64 p-4">
                    <p className="text-body-sm text-text-secondary">A floating panel.</p>
                  </PopoverContent>
                </Popover>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="secondary">Menu</Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuLabel>Actions</DropdownMenuLabel>
                    <DropdownMenuItem>View profile</DropdownMenuItem>
                    <DropdownMenuItem>Edit</DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem tone="danger">Deactivate</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                <Tooltip content="Confidence reflects how much history we have about this trainer.">
                  <Button variant="ghost" icon={<Info size={16} className="shrink-0" />}>
                    Tooltip
                  </Button>
                </Tooltip>

                <Button onClick={() => toast.success('Approved', { description: 'IP Mugisha is now allocated.' })}>
                  Fire toast
                </Button>
              </div>
            </Section>

            <Section title="Feedback & data states">
              <div className="grid gap-6 md:grid-cols-3">
                <div className="rounded-md border border-hairline p-4">
                  <div className="flex flex-col gap-3">
                    <Skeleton className="h-6 w-1/2" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                  </div>
                </div>
                <div className="rounded-md border border-hairline">
                  <EmptyState
                    compact
                    icon={<Filter size={20} className="shrink-0" />}
                    title="No training requests yet"
                    description="Create one to start matching trainers."
                    action={<Button size="sm">Create request</Button>}
                  />
                </div>
                <div className="rounded-md border border-hairline">
                  <ErrorState compact onRetry={() => toast('Retrying…')} />
                </div>
              </div>
              <Separator className="my-6" />
              <div className="flex flex-col gap-4">
                <Progress value={72} />
                <Pagination page={page} pageCount={12} total={812} pageSize={25} onPageChange={setPage} />
              </div>
            </Section>
          </div>
        </div>

        <CommandPalette
          open={paletteOpen}
          onOpenChange={setPaletteOpen}
          groups={[
            {
              heading: 'Navigate',
              commands: [
                { id: 'dash', label: 'Go to dashboard', run: () => toast('Dashboard') },
                { id: 'pred', label: 'Open prediction queue', run: () => toast('Predictions') },
              ],
            },
            {
              heading: 'Actions',
              commands: [{ id: 'new', label: 'Create training request', run: () => toast('New request') }],
            },
          ]}
        />
        <Toaster />
      </div>
    </TooltipProvider>
  );
}
