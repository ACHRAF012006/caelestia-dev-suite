.pragma library
// Angle deltas use Qt's 120 units/notch. Touchpad pixel deltas use 40 px/step.
// Direction reversals discard residual motion; each unit keeps its own accumulator.
function consume(residual, angle, pixels) {
    var amount = angle !== 0 ? angle / 120 : pixels / 40;
    if (residual * amount < 0) residual = 0;
    var total = residual + amount;
    var steps = total < 0 ? Math.ceil(total) : Math.floor(total);
    return { steps: steps, residual: total - steps };
}
