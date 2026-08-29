"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { setCompactMode } from "@/shared/store/preferences-slice";
import { useAppDispatch, useAppSelector } from "@/shared/store/hooks";

export function PreferencePanel() {
  const dispatch = useAppDispatch();
  const compactMode = useAppSelector((state) => state.preferences.compactMode);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Redux preference example</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center gap-3">
        <Checkbox
          id="compact-mode"
          checked={compactMode}
          onCheckedChange={(checked) => dispatch(setCompactMode(Boolean(checked)))}
        />
        <Label htmlFor="compact-mode">Use compact dashboard density</Label>
      </CardContent>
    </Card>
  );
}
