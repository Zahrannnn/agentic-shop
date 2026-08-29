"use client";

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { formatDistanceToNow } from "date-fns";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { WorkItem } from "../types";

const columns: ColumnDef<WorkItem>[] = [
  { accessorKey: "id", header: "ID" },
  { accessorKey: "name", header: "Name" },
  { accessorKey: "owner", header: "Owner" },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.original.status;
      const variant =
        status === "Healthy"
          ? "success"
          : status === "Watch"
            ? "warning"
            : "destructive";

      return <Badge variant={variant}>{status}</Badge>;
    },
  },
  {
    accessorKey: "updatedAt",
    header: "Updated",
    cell: ({ row }) =>
      formatDistanceToNow(new Date(row.original.updatedAt), { addSuffix: true }),
  },
];

export function WorkItemsTable({ data }: { data: WorkItem[] }) {
  "use no memo";

  // TanStack Table returns table helpers that React Compiler intentionally skips.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <Table>
      <TableHeader>
        {table.getHeaderGroups().map((headerGroup) => (
          <TableRow key={headerGroup.id}>
            {headerGroup.headers.map((header) => (
              <TableHead key={header.id}>
                {flexRender(header.column.columnDef.header, header.getContext())}
              </TableHead>
            ))}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow key={row.id}>
            {row.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
