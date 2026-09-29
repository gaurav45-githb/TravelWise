var people = 4;
function changePeople(n) { 
    people += n; if (people < 1) people = 1; if (people > 12) people = 12; 
    document.getElementById('people').value = people; document.getElementById('summary').innerText = people }


function toggleChoice(button) {
    button.classList.toggle('selected') }


function planTrip() { 
    var destination = document.getElementById('destination').value; 
    var budget = document.getElementById('budget').value; 
    document.getElementById('suggestion').innerText = destination.includes('Patna') ? 'Patna is better for historical places, culture, food and nature than beaches.' : 'Your preferences look good. We can generate a personalized trip.'; 
    document.getElementById('total').innerText = '₹' + Math.round(budget * .8925).toLocaleString('en-IN'); 
    document.getElementById('message').style.display = 'block'; 
        setTimeout(function () { 
            document.getElementById('message').style.display = 'none' }, 2000) 
        }
